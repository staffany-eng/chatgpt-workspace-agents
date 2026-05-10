#!/usr/bin/env python3
"""HubSpot MCP adapter for NurtureAny Sales Bot.

This server is intentionally V1-safe: read tools and dry-run previews only.
HubSpot write tools are not exposed until the write-back phase is approved.
"""

from __future__ import annotations

import hashlib
import html
import ipaddress
import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP


HUBSPOT_BASE_URL = "https://api.hubapi.com"
SUPPORTED_COUNTRIES = ("Singapore", "Malaysia", "Indonesia")
OVERALL_ADMINS = {"eugene@staffany.com", "kaiyi@staffany.com"}
REGIONAL_MANAGERS = {
    "kerren.fong@staffany.com": ("Singapore", "Malaysia"),
    "sarah@staffany.com": ("Indonesia",),
}

COMPANY_PROPERTIES = [
    "name",
    "domain",
    "hs_is_target_account",
    "hubspot_owner_id",
    "company_country",
    "numberofemployees",
    "industry",
    "contract_end_date",
    "current_tool_renewal_date",
    "notes_last_updated",
    "hs_num_decision_makers",
    "hs_num_contacts_with_buying_roles",
    "prospecting_account",
    "nurtureany_status",
    "nurtureany_priority_score",
    "nurtureany_segment",
    "nurtureany_next_action",
    "nurtureany_next_trigger_at",
    "nurtureany_last_reviewed_at",
    "nurtureany_last_nurtured_at",
    "nurtureany_enrichment_status",
    "nurtureany_contact_coverage",
]

CONTACT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "jobtitle",
    "job_role",
    "hs_buying_role",
    "hubspot_owner_id",
    "lastmodifieddate",
    "nurtureany_persona",
    "nurtureany_channel_fit",
    "nurtureany_contact_confidence",
    "nurtureany_last_verified_at",
]

DEAL_PROPERTIES = [
    "dealname",
    "dealstage",
    "pipeline",
    "amount",
    "closedate",
    "hubspot_owner_id",
    "contract_end_date",
]

TASK_PROPERTIES = [
    "hs_timestamp",
    "hs_task_subject",
    "hubspot_owner_id",
    "hs_task_status",
    "hs_task_priority",
    "hs_task_type",
    "hs_lastmodifieddate",
]

FREE_SEARCH_SOURCE_TYPES = (
    "company_website",
    "company_careers",
    "public_job_board",
    "general_web",
    "linkedin_manual",
    "google_maps_manual",
    "instagram_tiktok_manual",
    "facebook_manual",
    "review_site",
)
FETCHABLE_PUBLIC_SOURCE_TYPES = {"company_website", "company_careers", "public_job_board"}
MANUAL_ONLY_HOST_MARKERS = (
    "linkedin.com",
    "instagram.com",
    "tiktok.com",
    "facebook.com",
    "google.com",
    "maps.google.",
)
PUBLIC_FETCH_TIMEOUT_SECONDS = 5
PUBLIC_FETCH_MAX_BYTES = 30_000
PUBLIC_EVIDENCE_ITEM_LIMIT = 20
PUBLIC_TASK_ACCOUNT_LIMIT = 25
HUBSPOT_SEARCH_PAGE_LIMIT = 100
HUBSPOT_SEARCH_RESULT_LIMIT = 1000
TASK_ASSOCIATION_LIMIT = 100
TASK_RETURN_LIMIT = 100


mcp = FastMCP(
    "hubspot_nurtureany",
    instructions=(
        "Read-only HubSpot target-account tools for NurtureAny. "
        "Mutation tools are intentionally not exposed in V1."
    ),
)


class HubSpotError(RuntimeError):
    pass


class ScopeError(RuntimeError):
    pass


def _token() -> str:
    token = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise HubSpotError("Missing HUBSPOT_PRIVATE_APP_TOKEN.")
    return token


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    url = urllib.parse.urljoin(HUBSPOT_BASE_URL, path)
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "authorization": f"Bearer {_token()}",
        "accept": "application/json",
    }
    if data is not None:
        headers["content-type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)

    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            if error.code == 429 and attempt < 3:
                time.sleep(1.5 * (attempt + 1))
                continue
            detail = error.read().decode("utf-8", errors="replace")
            raise HubSpotError(f"HubSpot API failed: {error.code} {detail[:300]}") from error
        except urllib.error.URLError as error:
            raise HubSpotError(f"HubSpot API failed: {error.reason}") from error

    raise HubSpotError("HubSpot API rate-limited after retries.")


def _get(path: str, params: dict[str, str] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode(params or {})
    return _request_json("GET", f"{path}?{query}" if query else path)


def _post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", path, body)


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "HubSpot",
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def _owner_by_email(email: str) -> dict[str, Any] | None:
    normalized = _normalize_email(email)
    if not normalized:
        return None
    data = _get("/crm/v3/owners/", {"email": normalized, "archived": "false", "limit": "100"})
    for owner in data.get("results", []):
        if _normalize_email(owner.get("email", "")) == normalized:
            return owner
    return None


def _caller_scope(slack_user_email: str) -> dict[str, Any]:
    email = _normalize_email(slack_user_email)
    if not email:
        return {"kind": "blocked", "email": "", "countries": (), "owner_id": None}
    if email in OVERALL_ADMINS:
        return {"kind": "admin", "email": email, "countries": SUPPORTED_COUNTRIES, "owner_id": None}
    if email in REGIONAL_MANAGERS:
        return {"kind": "manager", "email": email, "countries": REGIONAL_MANAGERS[email], "owner_id": None}
    owner = _owner_by_email(email)
    if not owner:
        return {"kind": "blocked", "email": email, "countries": SUPPORTED_COUNTRIES, "owner_id": None}
    return {"kind": "ae", "email": email, "countries": SUPPORTED_COUNTRIES, "owner_id": str(owner["id"])}


def _safe_countries(countries: list[str] | None, allowed: tuple[str, ...]) -> list[str]:
    requested = countries or list(allowed)
    return [country for country in requested if country in allowed]


def _bounded_int(value: Any, default: int, minimum: int = 1, maximum: int = HUBSPOT_SEARCH_RESULT_LIMIT) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _company_search(filters: list[dict[str, Any]], limit: int = 20, after: str | None = None) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20)
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = after

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": COMPANY_PROPERTIES,
            "limit": page_limit,
            "sorts": [{"propertyName": "notes_last_updated", "direction": "DESCENDING"}],
        }
        if next_after:
            body["after"] = next_after

        page = _post("/crm/v3/objects/companies/search", body)
        if total is None and page.get("total") is not None:
            total = _int_value(page.get("total"))

        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = page.get("paging", {}).get("next", {}).get("after")
        if not page_results or not next_after:
            break

    returned_count = len(results)
    has_more = bool(next_after) or (total is not None and returned_count < total)
    return {
        "results": results,
        "total": total,
        "requested_limit": requested_limit,
        "returned_count": returned_count,
        "has_more": has_more,
        "truncated": has_more,
    }


def _target_filters(countries: list[str], owner_id: str | None = None) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_is_target_account", "operator": "EQ", "value": "true"},
        {"propertyName": "company_country", "operator": "IN", "values": countries},
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id})
    return filters


def _target_owner_id_for_scope(scope: dict[str, Any], owner_email: str | None = None) -> tuple[str | None, str]:
    target_email = _normalize_email(owner_email or "")
    if not target_email:
        return (str(scope["owner_id"]), scope["email"]) if scope["kind"] == "ae" and scope.get("owner_id") else (None, "")

    owner = _owner_by_email(target_email)
    if not owner:
        raise ScopeError(f"HubSpot owner not found for {target_email}.")

    owner_id = str(owner["id"])
    if scope["kind"] == "ae" and owner_id != scope.get("owner_id"):
        raise ScopeError("Caller is not authorized to inspect another owner's target accounts.")
    if scope["kind"] not in {"admin", "manager", "ae"}:
        raise ScopeError("Caller identity is not mapped to an allowed scope.")
    return owner_id, target_email


def _summarize_company(company: dict[str, Any]) -> dict[str, Any]:
    props = company.get("properties", {})
    decision_count = _int_value(props.get("hs_num_decision_makers"))
    buying_role_count = _int_value(props.get("hs_num_contacts_with_buying_roles"))
    contract_date = props.get("contract_end_date") or props.get("current_tool_renewal_date") or ""
    return {
        "company_id": company.get("id"),
        "name": props.get("name") or "",
        "domain": props.get("domain") or "",
        "country": props.get("company_country") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "headcount": props.get("numberofemployees") or "",
        "industry": props.get("industry") or "",
        "contract_or_renewal_date": contract_date,
        "last_activity_at": props.get("notes_last_updated") or "",
        "decision_maker_count": decision_count,
        "buying_role_contact_count": buying_role_count,
        "prospecting_account": props.get("prospecting_account") or "",
        "enrichment_status": _enrichment_status(props, contact_count=None),
        "missing_fields": _missing_company_fields(props, contact_count=None),
    }


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _date_value(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def _missing_company_fields(props: dict[str, Any], contact_count: int | None) -> list[str]:
    missing: list[str] = []
    if not props.get("hubspot_owner_id"):
        missing.append("company owner")
    if not props.get("company_country"):
        missing.append("country")
    if not props.get("numberofemployees"):
        missing.append("headcount")
    if not props.get("industry"):
        missing.append("industry")
    if not (props.get("contract_end_date") or props.get("current_tool_renewal_date")):
        missing.append("contract/renewal date")
    if contact_count == 0:
        missing.append("associated contact")
    if _int_value(props.get("hs_num_decision_makers")) < 1 and _int_value(props.get("hs_num_contacts_with_buying_roles")) < 1:
        missing.append("decision maker")
    return missing


def _enrichment_status(props: dict[str, Any], contact_count: int | None) -> str:
    missing = _missing_company_fields(props, contact_count)
    if missing:
        return "not_enriched"
    if props.get("nurtureany_channel_fit") or props.get("nurtureany_contact_coverage"):
        return "nurture_ready"
    return "minimum_enriched"


def _association_ids_with_metadata(from_type: str, object_id: str, to_type: str, limit: int = 20) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=TASK_ASSOCIATION_LIMIT)
    data = _get(
        f"/crm/v4/objects/{from_type}/{object_id}/associations/{to_type}",
        {"limit": str(requested_limit)},
    )
    ids = [str(item["toObjectId"]) for item in data.get("results", []) if item.get("toObjectId")]
    has_more = bool(data.get("paging", {}).get("next", {}).get("after"))
    return {"ids": ids, "has_more": has_more, "truncated": has_more, "requested_limit": requested_limit}


def _association_ids(from_type: str, object_id: str, to_type: str, limit: int = 20) -> list[str]:
    data = _association_ids_with_metadata(from_type, object_id, to_type, limit)
    return data["ids"]


def _batch_read(object_type: str, ids: list[str], properties: list[str]) -> list[dict[str, Any]]:
    if not ids:
        return []
    data = _post(
        f"/crm/v3/objects/{object_type}/batch/read",
        {
            "properties": properties,
            "inputs": [{"id": object_id} for object_id in ids[:100]],
        },
    )
    return data.get("results", [])


def _add_task_sources(
    task_sources: dict[str, list[dict[str, str]]],
    task_ids: list[str],
    source_type: str,
    source_id: str,
) -> None:
    for task_id in task_ids:
        sources = task_sources.setdefault(task_id, [])
        source = {"object_type": source_type, "object_id": str(source_id)}
        if source not in sources:
            sources.append(source)


def _collect_task_associations(company_id: str, contact_ids: list[str], deal_ids: list[str]) -> dict[str, Any]:
    task_sources: dict[str, list[dict[str, str]]] = {}
    truncated = False

    company_tasks = _association_ids_with_metadata("companies", company_id, "tasks", TASK_ASSOCIATION_LIMIT)
    _add_task_sources(task_sources, company_tasks["ids"], "company", company_id)
    truncated = truncated or company_tasks["truncated"]

    for contact_id in contact_ids:
        contact_tasks = _association_ids_with_metadata("contacts", contact_id, "tasks", TASK_ASSOCIATION_LIMIT)
        _add_task_sources(task_sources, contact_tasks["ids"], "contact", contact_id)
        truncated = truncated or contact_tasks["truncated"]

    for deal_id in deal_ids:
        deal_tasks = _association_ids_with_metadata("deals", deal_id, "tasks", TASK_ASSOCIATION_LIMIT)
        _add_task_sources(task_sources, deal_tasks["ids"], "deal", deal_id)
        truncated = truncated or deal_tasks["truncated"]

    return {"task_ids": list(task_sources.keys()), "task_sources": task_sources, "truncated": truncated}


def _is_incomplete_task(task: dict[str, Any]) -> bool:
    status = str(task.get("properties", {}).get("hs_task_status") or "").strip().upper()
    return status != "COMPLETED"


def _safe_task_summary(task: dict[str, Any], task_sources: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    props = task.get("properties", {})
    task_id = str(task.get("id") or "")
    return {
        "task_id": task_id,
        "due_at": props.get("hs_timestamp") or "",
        "subject": _short_text(str(props.get("hs_task_subject") or ""), 160),
        "owner_id": props.get("hubspot_owner_id") or "",
        "status": props.get("hs_task_status") or "",
        "priority": props.get("hs_task_priority") or "",
        "type": props.get("hs_task_type") or "",
        "last_modified_at": props.get("hs_lastmodifieddate") or "",
        "associated_via": task_sources.get(task_id, []),
    }


def _sort_tasks_by_due_at(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(task: dict[str, Any]) -> tuple[int, str]:
        due_at = task.get("due_at") or ""
        return (0 if due_at else 1, due_at)

    return sorted(tasks, key=key)


def _sales_followup_signals(tasks: list[dict[str, Any]], truncated: bool) -> dict[str, Any]:
    today = datetime.now(timezone.utc).date()
    dated_tasks = [(task, _date_value(task.get("due_at"))) for task in tasks]
    overdue_count = len([task for task, due in dated_tasks if due and due < today])
    due_dates = [task.get("due_at") for task, due in dated_tasks if due and task.get("due_at")]
    return {
        "sales_followup_task_count": len(tasks),
        "overdue_sales_followup_task_count": overdue_count,
        "next_sales_followup_due_at": min(due_dates) if due_dates else "",
        "sales_followup_task_truncated": bool(truncated),
        "existing_sales_followup_open": bool(tasks),
    }


def _sales_followup_task_context(
    company: dict[str, Any],
    contact_ids: list[str] | None = None,
    deal_ids: list[str] | None = None,
    task_limit: int = 20,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    company_owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
    if not company_id or not company_owner_id:
        return {"tasks": [], "signals": _sales_followup_signals([], False)}

    contact_ids = contact_ids if contact_ids is not None else _association_ids("companies", company_id, "contacts", 50)
    deal_ids = deal_ids if deal_ids is not None else _association_ids("companies", company_id, "deals", 20)
    association_data = _collect_task_associations(company_id, contact_ids, deal_ids)
    task_ids = association_data["task_ids"]
    task_read_ids = task_ids[:TASK_RETURN_LIMIT]
    raw_tasks = _batch_read("tasks", task_read_ids, TASK_PROPERTIES)
    truncated = bool(association_data["truncated"] or len(task_ids) > len(task_read_ids))

    sales_owned_tasks = []
    for task in raw_tasks:
        props = task.get("properties", {})
        if not _is_incomplete_task(task):
            continue
        if str(props.get("hubspot_owner_id") or "") != company_owner_id:
            continue
        sales_owned_tasks.append(_safe_task_summary(task, association_data["task_sources"]))

    sorted_tasks = _sort_tasks_by_due_at(sales_owned_tasks)
    requested_limit = _bounded_int(task_limit, default=20, maximum=TASK_RETURN_LIMIT)
    returned_tasks = sorted_tasks[:requested_limit]
    truncated = truncated or len(sorted_tasks) > requested_limit
    return {"tasks": returned_tasks, "signals": _sales_followup_signals(sorted_tasks, truncated)}


def _task_due_in_window(task: dict[str, Any], due_start: str = "", due_end: str = "") -> bool:
    due = _date_value(task.get("due_at"))
    start = _date_value(due_start)
    end = _date_value(due_end)
    if (start or end) and not due:
        return False
    if start and due and due < start:
        return False
    if end and due and due > end:
        return False
    return True


def _get_company(company_id: str) -> dict[str, Any]:
    props = ",".join(COMPANY_PROPERTIES)
    return _get(f"/crm/v3/objects/companies/{company_id}", {"properties": props})


def _has_company_access(company: dict[str, Any], scope: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    if props.get("company_country") not in scope.get("countries", ()):
        return False
    if scope["kind"] in {"admin", "manager"}:
        return True
    return scope["kind"] == "ae" and props.get("hubspot_owner_id") == scope.get("owner_id")


def _company_context(company_id: str, scope: dict[str, Any], task_limit: int = 20) -> dict[str, Any] | None:
    company = _get_company(company_id)
    if not _has_company_access(company, scope):
        return None
    contact_ids = _association_ids("companies", company_id, "contacts", 50)
    deal_ids = _association_ids("companies", company_id, "deals", 20)
    contacts = _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)
    deals = _batch_read("deals", deal_ids, DEAL_PROPERTIES)
    props = company.get("properties", {})
    safe_contacts = [_safe_contact(contact) for contact in contacts]
    task_context = _sales_followup_task_context(company, contact_ids, deal_ids, task_limit)
    company_summary = _summarize_company_with_contacts(company, safe_contacts)
    company_summary.update(task_context["signals"])
    return {
        "company": company_summary,
        "contacts": safe_contacts,
        "deals": [_safe_deal(deal) for deal in deals],
        "sales_followup_tasks": task_context["tasks"],
        "coverage": _coverage(props, safe_contacts),
    }


def _summarize_company_with_contacts(company: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    summary = _summarize_company(company)
    props = company.get("properties", {})
    summary["contact_count"] = len(contacts)
    summary["enrichment_status"] = _enrichment_status(props, len(contacts))
    summary["missing_fields"] = _missing_company_fields(props, len(contacts))
    return summary


def _safe_contact(contact: dict[str, Any]) -> dict[str, Any]:
    props = contact.get("properties", {})
    first = props.get("firstname") or ""
    last = props.get("lastname") or ""
    role = props.get("job_role") or props.get("jobtitle") or ""
    buying_role = props.get("hs_buying_role") or ""
    return {
        "contact_id": contact.get("id"),
        "display_name": " ".join(part for part in [first, last[:1] + "." if last else ""] if part).strip(),
        "persona": role,
        "buying_role": buying_role,
        "is_decision_maker": buying_role == "DECISION_MAKER" or _role_is_decision_maker(role),
        "last_verified_at": props.get("nurtureany_last_verified_at") or props.get("lastmodifieddate") or "",
        "channel_fit": props.get("nurtureany_channel_fit") or "",
        "contact_confidence": props.get("nurtureany_contact_confidence") or "",
    }


def _role_is_decision_maker(role: str) -> bool:
    text = role.lower()
    markers = ("founder", "owner", "director", "ceo", "chief", "boss")
    return any(marker in text for marker in markers) and "executive" not in text


def _safe_deal(deal: dict[str, Any]) -> dict[str, Any]:
    props = deal.get("properties", {})
    return {
        "deal_id": deal.get("id"),
        "dealname": props.get("dealname") or "",
        "stage": props.get("dealstage") or "",
        "amount": props.get("amount") or "",
        "close_date": props.get("closedate") or "",
        "contract_end_date": props.get("contract_end_date") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
    }


def _coverage(props: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    decision_makers = [contact for contact in contacts if contact.get("is_decision_maker")]
    channel_known = [contact for contact in contacts if contact.get("channel_fit")]
    return {
        "contact_count": len(contacts),
        "decision_maker_count": max(_int_value(props.get("hs_num_decision_makers")), len(decision_makers)),
        "buying_role_contact_count": _int_value(props.get("hs_num_contacts_with_buying_roles")),
        "channel_fit_known_count": len(channel_known),
        "summary": (
            "nurture-ready"
            if contacts and decision_makers and channel_known
            else "minimum coverage" if contacts and decision_makers else "needs enrichment"
        ),
    }


def _score_company(summary: dict[str, Any]) -> dict[str, Any]:
    score = 0
    reasons: list[str] = []
    missing = summary.get("missing_fields", [])
    renewal = _date_value(summary.get("contract_or_renewal_date"))
    today = datetime.now(timezone.utc).date()

    if renewal:
        days = (renewal - today).days
        if 0 <= days <= 90:
            score += 35
            reasons.append(f"contract/renewal in {days} days")
        elif 91 <= days <= 180:
            score += 20
            reasons.append(f"contract/renewal in {days} days")
    else:
        score += 10
        reasons.append("missing contract/renewal date")

    decision_count = summary.get("decision_maker_count", 0) or summary.get("buying_role_contact_count", 0)
    if decision_count:
        score += 20
        reasons.append("direct decision-maker coverage exists")
    else:
        score += 15
        reasons.append("missing decision-maker coverage")

    if summary.get("prospecting_account") == "true":
        score += 10
        reasons.append("marked as prospecting account")

    if summary.get("last_activity_at"):
        activity_date = _date_value(summary.get("last_activity_at"))
        if activity_date:
            age = (today - activity_date).days
            if age >= 21:
                score += 15
                reasons.append(f"no recent sales note for {age} days")
    else:
        score += 8
        reasons.append("missing recent activity date")

    overdue_tasks = _int_value(summary.get("overdue_sales_followup_task_count"))
    open_tasks = _int_value(summary.get("sales_followup_task_count"))
    next_task_due = _date_value(summary.get("next_sales_followup_due_at"))
    if overdue_tasks:
        score += 20
        reasons.append(f"{overdue_tasks} overdue sales follow-up task(s)")
    elif next_task_due:
        days_until_due = (next_task_due - today).days
        if 0 <= days_until_due <= 7:
            score += 12
            reasons.append(f"sales follow-up due in {days_until_due} days")
        elif open_tasks:
            score += 4
            reasons.append("open sales follow-up already scheduled")
    elif open_tasks:
        score += 4
        reasons.append("open sales follow-up already scheduled")

    score -= min(len(missing) * 3, 18)
    return {
        "priority_score": max(score, 0),
        "priority_reasons": reasons[:5],
        "segment": _segment(summary, reasons),
    }


def _segment(summary: dict[str, Any], reasons: list[str]) -> str:
    if _int_value(summary.get("overdue_sales_followup_task_count")):
        return "Overdue sales follow-up"
    if any("contract/renewal" in reason for reason in reasons):
        return "Renewal / contract-end alert"
    if "decision maker" in " ".join(summary.get("missing_fields", [])).lower():
        return "Missing direct contact"
    if summary.get("prospecting_account") == "true":
        return "Pre-demo target account"
    return "High-value dormant account"


def _scope_response(
    scope: dict[str, Any],
    countries: list[str],
    target_owner_id: str | None = None,
    target_owner_email: str = "",
) -> dict[str, Any]:
    response = {
        "caller_email": scope.get("email"),
        "scope_kind": scope.get("kind"),
        "countries": countries,
        "owner_id": scope.get("owner_id"),
    }
    if target_owner_id:
        response["target_owner_id"] = target_owner_id
    if target_owner_email:
        response["target_owner_email"] = target_owner_email
    return response


def _search_metadata(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "total": data.get("total"),
        "requested_limit": data.get("requested_limit"),
        "returned_count": data.get("returned_count", len(data.get("results", []))),
        "has_more": bool(data.get("has_more")),
        "truncated": bool(data.get("truncated")),
    }


def _coverage_caveat(data: dict[str, Any], base: str) -> str:
    if data.get("truncated"):
        total = data.get("total")
        returned = data.get("returned_count", len(data.get("results", [])))
        if total is not None:
            return f"{base} Only {returned} of {total} scoped accounts were returned; do not present counts as complete."
        return f"{base} Returned records are truncated; do not present counts as complete."
    return f"{base} Full scoped result set was returned."


def _safe_free_source_types(source_types: list[str] | None) -> list[str]:
    requested = source_types or list(FREE_SEARCH_SOURCE_TYPES)
    selected: list[str] = []
    for source_type in requested:
        normalized = str(source_type or "").strip().lower()
        if normalized in FREE_SEARCH_SOURCE_TYPES and normalized not in selected:
            selected.append(normalized)
    return selected


def _search_url(query: str) -> str:
    return "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)


def _job_board_query(company: dict[str, Any]) -> str:
    name = company.get("name", "")
    country = company.get("country", "")
    if country == "Singapore":
        return f'"{name}" hiring OR jobs site:mycareersfuture.gov.sg OR site:jobstreet.com.sg'
    if country == "Malaysia":
        return f'"{name}" hiring OR jobs site:myfuturejobs.gov.my OR site:jobstreet.com.my'
    if country == "Indonesia":
        return f'"{name}" hiring OR jobs site:jobstreet.co.id OR site:kalibrr.com'
    return f'"{name}" hiring OR jobs'


def _free_search_tasks_for_company(company: dict[str, Any], source_types: list[str]) -> list[dict[str, Any]]:
    name = company.get("name", "")
    country = company.get("country", "")
    domain = company.get("domain", "")
    missing = ", ".join(company.get("missing_fields", [])) or "public enrichment"
    task_templates = {
        "company_website": {
            "label": "Find official company website",
            "query": f'"{name}" official website {country}'.strip(),
            "reason": "Confirm official domain, outlet context, and public contact route.",
        },
        "company_careers": {
            "label": "Check official careers or hiring page",
            "query": f'"{name}" careers hiring jobs HR {country}'.strip(),
            "reason": "Hiring pages often expose HR routes and current manpower pain.",
        },
        "public_job_board": {
            "label": "Check public job boards",
            "query": _job_board_query(company),
            "reason": "Job listings can reveal active hiring, role pressure, and HR contacts.",
        },
        "general_web": {
            "label": "Search for decision makers and HR context",
            "query": f'"{name}" "HR" OR founder OR owner OR "operations director" {country}'.strip(),
            "reason": "General search can surface public profiles, articles, and company context.",
        },
        "linkedin_manual": {
            "label": "Manual LinkedIn people search",
            "query": f'site:linkedin.com "{name}" HR founder owner director {country}'.strip(),
            "reason": "Manual-only check for likely decision makers; do not scrape LinkedIn.",
        },
        "google_maps_manual": {
            "label": "Manual Google Maps and reviews check",
            "query": f'"{name}" {country} Google Maps owner manager reviews'.strip(),
            "reason": "Manual-only check for outlet count, owner replies, and operating signals.",
        },
        "instagram_tiktok_manual": {
            "label": "Manual Instagram/TikTok social check",
            "query": f'"{name}" Instagram TikTok hiring opening outlet'.strip(),
            "reason": "Manual-only check for openings, hiring posts, and outreach angles.",
        },
        "facebook_manual": {
            "label": "Manual Facebook public page check",
            "query": f'"{name}" Facebook hiring outlet opening'.strip(),
            "reason": "Manual-only check for public posts, outlet activity, and local context.",
        },
        "review_site": {
            "label": "Check public employee/customer review context",
            "query": f'"{name}" Glassdoor reviews hiring manpower HR'.strip(),
            "reason": "Review context can suggest pain angles but must be verified by AE.",
        },
    }
    tasks = []
    for source_type in source_types:
        template = task_templates[source_type]
        query = template["query"]
        tasks.append(
            {
                "source_type": source_type,
                "label": template["label"],
                "query": query,
                "url": _search_url(query),
                "reason": template["reason"],
                "gap_context": missing,
                "domain_hint": domain,
                "will_fetch_automatically": False,
                "requires_manual_review": True,
            }
        )
    return tasks


def _is_public_url(url: str) -> bool:
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
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return any(marker in host for marker in MANUAL_ONLY_HOST_MARKERS)


def _html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _fetch_public_evidence_text(source_type: str, url: str) -> tuple[str, str]:
    if source_type not in FETCHABLE_PUBLIC_SOURCE_TYPES:
        return "", "skipped_manual_source"
    if not url:
        return "", "skipped_no_url"
    if not _is_public_url(url) or _is_manual_only_host(url):
        return "", "skipped_unsafe_or_manual_url"
    request = urllib.request.Request(
        url,
        headers={
            "accept": "text/html,text/plain;q=0.9,*/*;q=0.1",
            "user-agent": "StaffAny-NurtureAny/1.0 public-evidence-review",
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
            text = _html_to_text(raw[:PUBLIC_FETCH_MAX_BYTES].decode("utf-8", errors="replace"))
            return text, status
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return "", f"fetch_failed:{str(error)[:80]}"


def _raw_contacts_for_company(company_id: str) -> list[dict[str, Any]]:
    contact_ids = _association_ids("companies", company_id, "contacts", 100)
    return _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)


def _normalize_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def _safe_email(value: str) -> str:
    email = (value or "").strip().lower()
    if not email or not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        return ""
    return email


def _candidate_from_evidence(item: dict[str, Any], source_type: str, source_url: str) -> dict[str, Any] | None:
    candidate = item.get("contact_candidate") if isinstance(item.get("contact_candidate"), dict) else item
    name = str(candidate.get("name") or candidate.get("contact_name") or "").strip()
    title = str(candidate.get("title") or candidate.get("jobtitle") or candidate.get("job_title") or "").strip()
    email = _safe_email(str(candidate.get("email") or ""))
    if not (name or email):
        return None
    result = {
        "display_name": name,
        "persona": title,
        "email": email,
        "source_type": source_type,
        "source_url": source_url,
        "is_decision_maker": _role_is_decision_maker(title),
        "confidence": "needs-check",
    }
    if candidate.get("phone") or candidate.get("phone_number"):
        result["omitted_fields"] = ["phone"]
    return result


def _contact_full_name(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return " ".join(part for part in [props.get("firstname") or "", props.get("lastname") or ""] if part).strip()


def _dedupe_candidate(candidate: dict[str, Any], existing_contacts: list[dict[str, Any]]) -> dict[str, Any]:
    candidate_email = _safe_email(candidate.get("email", ""))
    candidate_name = _normalize_name(candidate.get("display_name", ""))
    for contact in existing_contacts:
        props = contact.get("properties", {})
        existing_email = _safe_email(props.get("email") or "")
        if candidate_email and existing_email and candidate_email == existing_email:
            return {
                "status": "likely_existing_contact",
                "matched_contact_id": contact.get("id"),
                "reason": "email exact match",
            }
    for contact in existing_contacts:
        existing_name = _normalize_name(_contact_full_name(contact))
        if candidate_name and existing_name and candidate_name == existing_name:
            return {
                "status": "possible_existing_contact",
                "matched_contact_id": contact.get("id"),
                "reason": "name exact match; review before write-back",
            }
    return {"status": "new_candidate", "matched_contact_id": "", "reason": "no HubSpot contact match found"}


def _short_text(value: str, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:limit].rstrip()


def _extract_company_signals(item: dict[str, Any], source_type: str, source_url: str, fetched_text: str) -> list[dict[str, Any]]:
    text = " ".join(
        str(part or "")
        for part in [
            item.get("title"),
            item.get("snippet"),
            item.get("description"),
            fetched_text,
        ]
    )
    lowered = text.lower()
    signal_keywords = {
        "hiring_signal": ("hiring", "career", "careers", "job", "vacancy", "recruit", "join our team", "open role"),
        "growth_signal": ("new outlet", "opening", "expanding", "expansion", "launch", "coming soon"),
        "pain_signal": ("manpower", "understaffed", "turnover", "attendance", "payroll", "scheduling", "retention"),
    }
    signals = []
    for signal_type, keywords in signal_keywords.items():
        matched = [keyword for keyword in keywords if keyword in lowered]
        if matched:
            signals.append(
                {
                    "signal_type": signal_type,
                    "keywords": matched[:5],
                    "source_type": source_type,
                    "source_url": source_url,
                    "evidence": _short_text(item.get("snippet") or fetched_text or item.get("title") or ""),
                    "confidence": "needs-check",
                }
            )
    return signals


def _outreach_angles(signals: list[dict[str, Any]], candidates: list[dict[str, Any]]) -> list[str]:
    signal_types = {signal.get("signal_type") for signal in signals}
    angles = []
    if "hiring_signal" in signal_types:
        angles.append("Use active hiring as the reason to ask about onboarding, scheduling, and HR admin load.")
    if "growth_signal" in signal_types:
        angles.append("Use expansion or new outlet context to ask how they are scaling workforce operations.")
    if "pain_signal" in signal_types:
        angles.append("Use public manpower or operations pain only as a soft discovery prompt, not as a claim.")
    if any(candidate.get("is_decision_maker") for candidate in candidates):
        angles.append("Review the decision-maker candidate before drafting a manual LinkedIn or WhatsApp touch.")
    return angles[:5]


@mcp.tool()
def list_my_target_accounts(slack_user_email: str, limit: int = 20) -> dict[str, Any]:
    """List target accounts owned by the requesting AE."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked" or not scope.get("owner_id"):
            return _blocked("Slack email is not mapped to a HubSpot owner.", {"caller_email": slack_user_email})
        countries = list(scope["countries"])
        data = _company_search(_target_filters(countries, scope["owner_id"]), limit)
        accounts = [_summarize_company(company) for company in data.get("results", [])]
        return {
            "answer": accounts,
            "source": "HubSpot companies search",
            "scope": _scope_response(scope, countries),
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": _coverage_caveat(data, "HubSpot target-account list."),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_team_target_accounts(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """List target accounts for an authorized manager/admin regional scope."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] not in {"admin", "manager"}:
            return _blocked("Caller is not authorized for manager team scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        data = _company_search(_target_filters(selected, target_owner_id), limit)
        accounts = [_summarize_company(company) for company in data.get("results", [])]
        return {
            "answer": accounts,
            "source": "HubSpot companies search",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": _coverage_caveat(data, "Manager scope is country-based."),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_account_context(slack_user_email: str, company_id: str) -> dict[str, Any]:
    """Get safe account context for one scoped HubSpot company."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _company_context(str(company_id), scope)
        if context is None:
            return _blocked("Company is outside caller scope.", {"caller_email": slack_user_email, "company_id": company_id})
        return {
            "answer": context,
            "source": "HubSpot company, contact, deal, and sales-owned task associations",
            "scope": _scope_response(scope, [context["company"]["country"]]),
            "confidence": "verified",
            "caveat": "Contact details and sales-owned follow-up tasks are summarized; raw phone numbers, task bodies, and exports are omitted.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id})


@mcp.tool()
def list_sales_followup_tasks(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
    due_start: str = "",
    due_end: str = "",
) -> dict[str, Any]:
    """List existing incomplete sales-owned follow-up tasks for scoped HubSpot target accounts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        requested_limit = _bounded_int(limit, default=50, maximum=TASK_RETURN_LIMIT)
        contexts: list[dict[str, Any]] = []
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""

        if company_ids:
            account_limit = _bounded_int(requested_limit, default=50, maximum=50)
            for company_id in company_ids[:account_limit]:
                context = _company_context(str(company_id), scope, task_limit=TASK_RETURN_LIMIT)
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope.")
                contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": account_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > account_limit,
                "truncated": len(company_ids) > account_limit,
            }
        else:
            if not selected:
                return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            data = _company_search(_target_filters(selected, target_owner_id), requested_limit)
            metadata = _search_metadata(data)
            for company in data.get("results", []):
                company_id = str(company.get("id") or "")
                if company_id:
                    context = _company_context(company_id, scope, task_limit=TASK_RETURN_LIMIT)
                    if context:
                        contexts.append(context)

        tasks = []
        task_truncated = bool(metadata.get("truncated"))
        for context in contexts:
            company = context["company"]
            task_truncated = task_truncated or bool(company.get("sales_followup_task_truncated"))
            for task in context.get("sales_followup_tasks", []):
                if not _task_due_in_window(task, due_start, due_end):
                    continue
                tasks.append(
                    {
                        "company_id": company.get("company_id"),
                        "company_name": company.get("name"),
                        "country": company.get("country"),
                        **task,
                    }
                )

        sorted_tasks = _sort_tasks_by_due_at(tasks)
        returned_tasks = sorted_tasks[:requested_limit]
        task_truncated = task_truncated or len(sorted_tasks) > requested_limit
        scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
        if due_start:
            scope_response["due_start"] = due_start
        if due_end:
            scope_response["due_end"] = due_end
        return {
            "answer": returned_tasks,
            "source": "HubSpot sales-owned task associations",
            "scope": scope_response,
            **metadata,
            "task_count": len(sorted_tasks),
            "returned_task_count": len(returned_tasks),
            "task_truncated": task_truncated,
            "confidence": "needs-check" if task_truncated else "verified",
            "caveat": (
                "Existing incomplete sales-owned HubSpot tasks only. Safe task summaries omit task body and do not create or mutate tasks."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def score_nurture_accounts(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 20,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Score scoped target accounts for nurture priority."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        contexts: list[dict[str, Any]] = []
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""
        if company_ids:
            requested_limit = _bounded_int(limit, default=20, maximum=50)
            for company_id in company_ids[:requested_limit]:
                context = _company_context(str(company_id), scope)
                if context:
                    contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": requested_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > requested_limit,
                "truncated": len(company_ids) > requested_limit,
            }
        else:
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            data = _company_search(_target_filters(selected, target_owner_id), limit)
            metadata = _search_metadata(data)
            for company in data.get("results", []):
                summary = _summarize_company(company)
                task_context = _sales_followup_task_context(company, task_limit=5)
                summary.update(task_context["signals"])
                contexts.append(
                    {
                        "company": summary,
                        "contacts": [],
                        "deals": [],
                        "sales_followup_tasks": task_context["tasks"],
                        "coverage": {},
                    }
                )

        ranked = []
        for context in contexts:
            company = context["company"]
            score = _score_company(company)
            ranked.append({**company, **score})
        ranked.sort(key=lambda item: item["priority_score"], reverse=True)
        task_truncated = any(item.get("sales_followup_task_truncated") for item in ranked)
        return {
            "answer": ranked,
            "source": "HubSpot account context scoring",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **metadata,
            "confidence": "needs-check"
            if metadata.get("truncated") or task_truncated or any(item.get("missing_fields") for item in ranked)
            else "verified",
            "caveat": _coverage_caveat(
                {**metadata, "truncated": bool(metadata.get("truncated") or task_truncated)},
                "Scoring uses HubSpot fields only unless C360/Luma context is separately supplied.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def find_contact_gaps(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 50,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Find target accounts missing contact, persona, channel, or decision-maker coverage."""

    scored = score_nurture_accounts(slack_user_email, None, countries, limit, owner_email)
    if scored.get("confidence") == "blocked":
        return scored
    gaps = []
    for account in scored.get("answer", []):
        missing = account.get("missing_fields", [])
        if any(field in missing for field in ["associated contact", "decision maker"]) or account.get("enrichment_status") != "nurture_ready":
            gaps.append(
                {
                    "company_id": account.get("company_id"),
                    "name": account.get("name"),
                    "country": account.get("country"),
                    "enrichment_status": account.get("enrichment_status"),
                    "missing_fields": missing,
                }
            )
    return {
        "answer": gaps,
        "source": scored.get("source"),
        "scope": scored.get("scope"),
        "gap_count": len(gaps),
        "scored_account_count": scored.get("returned_count", len(scored.get("answer", []))),
        "total": scored.get("total"),
        "requested_limit": scored.get("requested_limit"),
        "returned_count": scored.get("returned_count"),
        "has_more": scored.get("has_more"),
        "truncated": scored.get("truncated"),
        "confidence": scored.get("confidence"),
        "caveat": _coverage_caveat(
            scored,
            "Raw contact details are omitted; this is a coverage summary.",
        ),
    }


@mcp.tool()
def generate_free_search_tasks(
    slack_user_email: str,
    company_ids: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = 20,
    source_types: list[str] | None = None,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Generate free/manual public-search tasks for scoped HubSpot enrichment gaps."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected_sources = _safe_free_source_types(source_types)
        if not selected_sources:
            return _blocked("No supported free public source_types requested.", _scope_response(scope, []))

        contexts: list[dict[str, Any]] = []
        capped_limit = _bounded_int(limit, default=20, maximum=PUBLIC_TASK_ACCOUNT_LIMIT)
        metadata: dict[str, Any]
        selected = _safe_countries(countries, scope["countries"])
        target_owner_id = ""
        target_owner_email = ""
        if company_ids:
            for company_id in company_ids[:capped_limit]:
                context = _company_context(str(company_id), scope)
                if context:
                    contexts.append(context)
            metadata = {
                "total": len(company_ids),
                "requested_limit": capped_limit,
                "returned_count": len(contexts),
                "has_more": len(company_ids) > capped_limit,
                "truncated": len(company_ids) > capped_limit,
            }
        else:
            if not selected:
                return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
            target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
            data = _company_search(_target_filters(selected, target_owner_id), capped_limit)
            metadata = _search_metadata(data)
            for company in data.get("results", []):
                company_id = str(company.get("id") or "")
                if company_id:
                    context = _company_context(company_id, scope)
                    if context:
                        contexts.append(context)

        accounts = []
        for context in contexts:
            company = context["company"]
            coverage = context.get("coverage", {})
            missing = company.get("missing_fields", [])
            needs_public_enrichment = (
                bool(missing)
                or company.get("enrichment_status") != "nurture_ready"
                or coverage.get("channel_fit_known_count", 0) < 1
            )
            if not needs_public_enrichment and not company_ids:
                continue
            accounts.append(
                {
                    "company_id": company.get("company_id"),
                    "name": company.get("name"),
                    "country": company.get("country"),
                    "enrichment_status": company.get("enrichment_status"),
                    "missing_fields": missing,
                    "coverage": coverage,
                    "tasks": _free_search_tasks_for_company(company, selected_sources),
                }
            )

        return {
            "answer": accounts,
            "source": "HubSpot scoped gaps plus free public search task templates",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            **metadata,
            "confidence": "needs-check",
            "caveat": _coverage_caveat(
                metadata,
                "Tasks are manual/free. No paid API, social scraping, PII reveal, HubSpot mutation, or external message send was performed.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def review_public_enrichment_evidence(
    slack_user_email: str,
    company_id: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any]:
    """Review public evidence snippets/URLs and dedupe contact candidates against HubSpot."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        context = _company_context(str(company_id), scope)
        if context is None:
            return _blocked("Company is outside caller scope.", {"caller_email": slack_user_email, "company_id": company_id})
        if not evidence_items:
            return _blocked("No public evidence items were provided for review.", _scope_response(scope, [context["company"]["country"]]))

        existing_contacts = _raw_contacts_for_company(str(company_id))
        reviewed_evidence = []
        candidate_contacts = []
        company_signals = []

        for raw_item in evidence_items[:PUBLIC_EVIDENCE_ITEM_LIMIT]:
            if not isinstance(raw_item, dict):
                continue
            item = raw_item
            source_type = str(item.get("source_type") or "").strip().lower()
            if source_type not in FREE_SEARCH_SOURCE_TYPES:
                source_type = "general_web"
            source_url = str(item.get("url") or item.get("source_url") or "").strip()
            fetched_text, fetch_status = _fetch_public_evidence_text(source_type, source_url)
            signals = _extract_company_signals(item, source_type, source_url, fetched_text)
            company_signals.extend(signals)

            candidate = _candidate_from_evidence(item, source_type, source_url)
            if candidate:
                candidate["dedupe"] = _dedupe_candidate(candidate, existing_contacts)
                candidate_contacts.append(candidate)

            reviewed_evidence.append(
                {
                    "source_type": source_type,
                    "source_url": source_url,
                    "title": _short_text(str(item.get("title") or ""), 160),
                    "observed_at": str(item.get("observed_at") or ""),
                    "fetch_status": fetch_status,
                    "signals_found": [signal["signal_type"] for signal in signals],
                }
            )

        dedupe_summary = {
            "likely_existing_contact_count": len(
                [
                    candidate
                    for candidate in candidate_contacts
                    if candidate.get("dedupe", {}).get("status") == "likely_existing_contact"
                ]
            ),
            "possible_existing_contact_count": len(
                [
                    candidate
                    for candidate in candidate_contacts
                    if candidate.get("dedupe", {}).get("status") == "possible_existing_contact"
                ]
            ),
            "new_candidate_count": len(
                [candidate for candidate in candidate_contacts if candidate.get("dedupe", {}).get("status") == "new_candidate"]
            ),
        }

        return {
            "answer": {
                "company": context["company"],
                "reviewed_evidence": reviewed_evidence,
                "candidate_contacts": candidate_contacts,
                "company_signals": company_signals[:20],
                "outreach_angles": _outreach_angles(company_signals, candidate_contacts),
                "dedupe_summary": dedupe_summary,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot scoped account context plus reviewed public evidence",
            "scope": _scope_response(scope, [context["company"]["country"]]),
            "confidence": "needs-check",
            "caveat": "Public evidence is review-only. Social/gated sources are not fetched, and no HubSpot mutation or external message send was performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id})


@mcp.tool()
def draft_nurture_message(
    account_name: str,
    segment: str,
    persona: str = "",
    channel: str = "WhatsApp",
    trigger: str = "",
    locale: str = "neutral",
) -> dict[str, Any]:
    """Draft manual-review nurture copy. This tool never sends external messages."""

    safe_channel = channel if channel in {"WhatsApp", "email", "LinkedIn"} else "WhatsApp"
    greeting = "Hi" if safe_channel != "email" else "Hi there"
    persona_text = f" for your {persona} team" if persona else ""
    trigger_text = f" Saw that {trigger}." if trigger else ""
    if safe_channel == "email":
        draft = (
            f"Subject: Quick check-in on {account_name}\n\n"
            f"{greeting},\n\n"
            f"I wanted to check in on {account_name}{persona_text}.{trigger_text} "
            "Happy to share a few practical ideas if this is useful.\n\n"
            "Best,\n"
            "<AE name>"
        )
    elif safe_channel == "LinkedIn":
        draft = (
            f"{greeting}, noticed {account_name} is on our target-account list."
            f"{trigger_text} Open to a quick exchange on what your team is prioritising?"
        )
    else:
        draft = (
            f"{greeting}, checking in on {account_name}{persona_text}."
            f"{trigger_text} Would it be useful if I shared a few quick ideas?"
        )
    return {
        "answer": {
            "account_name": account_name,
            "segment": segment,
            "channel": safe_channel,
            "draft": draft,
        },
        "source": "NurtureAny drafting playbook",
        "scope": {"external_message_sending": False, "locale": locale},
        "confidence": "needs-check",
        "caveat": "Draft only; AE must review and send manually.",
    }


@mcp.tool()
def plan_hubspot_writeback(
    slack_user_email: str,
    selected_actions: list[dict[str, Any]],
    approval_marker: str = "",
) -> dict[str, Any]:
    """Create a dry-run HubSpot write-back plan. This tool does not mutate HubSpot."""

    scope = _caller_scope(slack_user_email)
    if scope["kind"] == "blocked":
        return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
    payload = json.dumps(
        {
            "caller": scope.get("email"),
            "actions": selected_actions,
            "approval_marker": approval_marker,
            "date": datetime.now(timezone.utc).isoformat(),
        },
        sort_keys=True,
    )
    preview_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    preview = []
    for action in selected_actions[:50]:
        source = action.get("source") if isinstance(action.get("source"), dict) else {}
        source_evidence = action.get("source_evidence") or source
        preview.append(
            {
                "company_id": action.get("company_id"),
                "contact_id": action.get("contact_id"),
                "task": action.get("task"),
                "note_summary": action.get("note_summary"),
                "field_updates": action.get("field_updates", {}),
                "source_evidence": source_evidence,
                "source_type": action.get("source_type") or source.get("type"),
                "source_url": action.get("source_url") or source.get("url"),
                "confidence": action.get("confidence", "needs-check"),
                "selected": bool(action.get("selected", True)),
            }
        )
    return {
        "answer": {
            "preview_id": preview_id,
            "actions": preview,
            "will_mutate_hubspot": False,
        },
        "source": "NurtureAny HubSpot write-back dry run",
        "scope": _scope_response(scope, list(scope.get("countries", ()))),
        "confidence": "verified",
        "caveat": "Preview only. Mutation tools are disabled in V1 until explicit write phase approval.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
