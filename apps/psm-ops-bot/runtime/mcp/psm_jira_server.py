#!/usr/bin/env python3
"""Jira PCO MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

mcp = FastMCP(
    "psm_jira",
    instructions=(
        "PCO Jira Service Management task adapter for PSM Ops Bot. "
        "Uses preconfigured fields only and fails closed when config is missing."
    ),
)

ALLOWED_STATUSES = {
    "open": "Open",
    "waiting customer": "Waiting Customer",
    "waiting internal": "Waiting Internal",
    "scheduled": "Scheduled",
    "done": "Done",
    "cancelled": "Cancelled",
}

STATUS_TRANSITION_CANDIDATES = {
    key: {label.lower()} for key, label in ALLOWED_STATUSES.items()
}
STATUS_TRANSITION_CANDIDATES["waiting customer"].add("pending customer")
STATUS_TRANSITION_CANDIDATES["waiting internal"].update(
    {"pending internal", "pending internal team"}
)

REQUEST_TYPE_ENVS = {
    "customer_next_action": "PSM_OPS_JIRA_REQUEST_TYPE_CUSTOMER_NEXT_ACTION",
    "onboarding_task": "PSM_OPS_JIRA_REQUEST_TYPE_ONBOARDING_TASK",
    "data_hygiene": "PSM_OPS_JIRA_REQUEST_TYPE_DATA_HYGIENE",
    "handoff_package": "PSM_OPS_JIRA_REQUEST_TYPE_HANDOFF_PACKAGE",
}

THIN_POC_MODE = "thin_poc"
THIN_POC_SERVICE_DESK_ID = "70"
THIN_POC_REQUEST_TYPES = {
    "customer_next_action": "81",
    "onboarding_task": "82",
    "data_hygiene": "83",
    "handoff_package": "",
}
THIN_POC_FIELD_IDS = {
    "staffany_orgs": "customfield_10667",
    "ps_team": "customfield_10876",
}
REMINDER_NOT_CONFIGURED = "Reminder at field is not configured in PCO yet."

FIELD_ENVS = {
    "customer": "PSM_OPS_JIRA_FIELD_CUSTOMER",
    "staffany_orgs": "PSM_OPS_JIRA_FIELD_STAFFANY_ORGS",
    "owner_psm": "PSM_OPS_JIRA_FIELD_OWNER_PSM",
    "contributor_cse": "PSM_OPS_JIRA_FIELD_CONTRIBUTOR_CSE",
    "action_type": "PSM_OPS_JIRA_FIELD_ACTION_TYPE",
    "risk_reason": "PSM_OPS_JIRA_FIELD_RISK_REASON",
    "source_links": "PSM_OPS_JIRA_FIELD_SOURCE_LINKS",
    "reminder_at": "PSM_OPS_JIRA_FIELD_REMINDER_AT",
}

SAFE_FIELDS = [
    "summary",
    "status",
    "priority",
    "assignee",
    "reporter",
    "created",
    "updated",
    "duedate",
    "issuetype",
]


class JiraError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _jira_mode() -> str:
    return _env("PSM_OPS_JIRA_MODE", "full").lower()


def _is_thin_poc() -> bool:
    return _jira_mode() == THIN_POC_MODE


def _jira_base_url() -> str:
    value = _env("JIRA_BASE_URL", "https://staffany.atlassian.net").rstrip("/")
    if not value:
        raise JiraError("JIRA_BASE_URL is not configured.")
    return value


def _basic_auth_header() -> str:
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    if not email or not token:
        raise JiraError("JIRA_EMAIL and JIRA_API_TOKEN must be configured.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Authorization": _basic_auth_header(),
        "Content-Type": "application/json",
    }


def _project_key() -> str:
    return _env("PSM_OPS_JIRA_PROJECT_KEY", "PCO") or "PCO"


def _service_desk_id() -> str:
    value = _env("PSM_OPS_JIRA_SERVICE_DESK_ID")
    if not value and _is_thin_poc():
        return THIN_POC_SERVICE_DESK_ID
    if not value:
        raise JiraError("PSM_OPS_JIRA_SERVICE_DESK_ID is not configured.")
    return value


def _request_type_id(key: str) -> str:
    env_name = REQUEST_TYPE_ENVS.get(key)
    if not env_name:
        raise JiraError(f"Unsupported request type key: {key}")
    value = _env(env_name)
    if not value and _is_thin_poc():
        thin_value = THIN_POC_REQUEST_TYPES.get(key, "")
        if thin_value:
            return thin_value
        raise JiraError("Handoff Package is disabled in thin_poc mode until a PCO request type exists.")
    if not value:
        raise JiraError(f"{env_name} is not configured.")
    return value


def _field_id(key: str) -> str:
    env_name = FIELD_ENVS[key]
    value = _env(env_name)
    if not value and _is_thin_poc():
        if key == "staffany_orgs":
            return THIN_POC_FIELD_IDS["staffany_orgs"]
        if key == "reminder_at":
            raise JiraError(REMINDER_NOT_CONFIGURED)
    if not value:
        raise JiraError(f"{env_name} is not configured.")
    return value


def _field_ids() -> dict[str, str]:
    return {key: _field_id(key) for key in FIELD_ENVS}


def _optional_field_id(key: str) -> str:
    try:
        return _field_id(key)
    except JiraError:
        return ""


def _ps_team_field_id() -> str:
    return _env("PSM_OPS_JIRA_FIELD_PS_TEAM") or THIN_POC_FIELD_IDS["ps_team"]


def _configured_fields() -> dict[str, str]:
    if _is_thin_poc():
        return {
            "staffany_orgs": _field_id("staffany_orgs"),
            "ps_team": _ps_team_field_id(),
        }
    return _field_ids()


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": "Jira PCO",
        "scope": scope,
        "confidence": "blocked",
        "caveat": message,
    }


def _verified(answer: Any, scope: dict[str, Any], caveat: str = "None.") -> dict[str, Any]:
    return {
        "answer": answer,
        "source": "Jira PCO",
        "scope": scope,
        "confidence": "verified",
        "caveat": caveat,
    }


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    url = f"{_jira_base_url()}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise JiraError(f"Jira API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise JiraError(f"Jira API unavailable: {error.reason}") from error


def _load_policy() -> dict[str, Any]:
    path = _env("PSM_OPS_ACCESS_POLICY_PATH")
    if not path:
        return {"users": []}
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as error:
        raise JiraError(f"Unable to read PSM_OPS_ACCESS_POLICY_PATH: {error}") from error
    except json.JSONDecodeError as error:
        raise JiraError(f"Invalid PSM_OPS_ACCESS_POLICY_PATH JSON: {error}") from error


def _normalize_slack_email(value: str) -> str:
    raw = (value or "").strip().lower()
    if not raw:
        return ""
    mailto = re.search(r"<mailto:([^|>]+)(?:\|[^>]*)?>", raw)
    if mailto:
        return mailto.group(1).strip().lower()
    bare = re.search(r"[\w.+-]+@[\w.-]+\.[a-z]{2,}", raw)
    if bare:
        return bare.group(0).strip().lower()
    return raw


def _jira_email_for_slack(email: str) -> str:
    aliases = {
        "kai.yi@staffany.com": "kaiyi@staffany.com",
        "leekai.yi@staffany.com": "kaiyi@staffany.com",
    }
    for mapping in _env("PSM_OPS_JIRA_EMAIL_ALIASES").split(","):
        if "=" not in mapping:
            continue
        source, target = mapping.split("=", 1)
        source_email = source.strip().lower()
        target_email = target.strip().lower()
        if source_email and target_email:
            aliases[source_email] = target_email
    return aliases.get(email, email)


def _caller(slack_user_email: str) -> dict[str, Any]:
    email = _normalize_slack_email(slack_user_email)
    jira_email = _jira_email_for_slack(email)
    if not email:
        raise JiraError("Caller Slack email is required.")
    policy = _load_policy()
    for user in policy.get("users", []):
        if str(user.get("slack_email", "")).strip().lower() == email and user.get("active", True):
            account_id = str(user.get("jira_account_id", "")).strip()
            if not account_id:
                raise JiraError(f"Jira account ID is missing for {email}.")
            return {
                "slack_email": email,
                "jira_account_id": account_id,
                "display_name": user.get("display_name") or email,
            }
    if _is_thin_poc():
        caller = _jira_user_by_email(jira_email)
        caller["slack_email"] = email
        caller["jira_email"] = jira_email
        return caller
    raise JiraError(f"No active Jira account mapping for {email}.")


def _jira_user_by_email(email: str) -> dict[str, Any]:
    query = urllib.parse.urlencode({"query": email, "maxResults": "10"})
    payload = _request_json("GET", f"/rest/api/3/user/search?{query}")
    users = payload if isinstance(payload, list) else []
    selected = next(
        (
            user
            for user in users
            if user.get("active", True)
            and str(user.get("emailAddress", "")).strip().lower() == email
        ),
        None,
    ) or next((user for user in users if user.get("active", True)), None)
    if not selected or not selected.get("accountId"):
        raise JiraError(f"No active Jira account mapping for {email}.")
    return {
        "slack_email": email,
        "jira_account_id": str(selected["accountId"]),
        "display_name": selected.get("displayName") or email,
    }


def _quote_jql(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _jql_field_ref(field_id: str) -> str:
    match = re.fullmatch(r"customfield_(\d+)", field_id)
    return f"cf[{match.group(1)}]" if match else field_id


def _search_issues(jql: str, fields: list[str], max_results: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "jql": jql,
            "fields": ",".join(fields),
            "maxResults": str(max(1, min(max_results, 100))),
        }
    )
    payload = _request_json("GET", f"/rest/api/3/search/jql?{query}")
    return payload.get("issues", []) if isinstance(payload, dict) else []


def _safe_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    reminder_field = _optional_field_id("reminder_at")
    return {
        "issue_key": issue.get("key", ""),
        "url": f"{_jira_base_url()}/browse/{issue.get('key', '')}",
        "summary": fields.get("summary") or issue.get("key", ""),
        "status": (fields.get("status") or {}).get("name", "Not set"),
        "priority": (fields.get("priority") or {}).get("name", "Not set"),
        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "due_date": fields.get("duedate") or "Not set",
        "updated": fields.get("updated") or "",
        "request_type": (fields.get("issuetype") or {}).get("name", "Not set"),
        "reminder_at": fields.get(reminder_field) if reminder_field else "Automatic from due date",
    }


def _description_from_draft(draft: dict[str, Any]) -> str:
    lines = [
        f"Customer: {draft.get('customer', '')}",
        f"Owner PSM: {draft.get('owner_psm', '')}",
        f"Contributor CSE: {draft.get('contributor_cse', '') or 'Not set'}",
        f"Action type: {draft.get('action_type', '')}",
        f"Risk reason: {draft.get('risk_reason', '') or 'Not set'}",
        "Source links:",
    ]
    source_links = draft.get("source_links") or []
    if source_links:
        lines.extend(f"- {link}" for link in source_links)
    else:
        lines.append("- Not set")
    return "\n".join(lines)


def _request_field_values(draft: dict[str, Any]) -> dict[str, Any]:
    if _is_thin_poc():
        values: dict[str, Any] = {"summary": draft["summary"]}
        if draft.get("staffany_orgs"):
            values[_field_id("staffany_orgs")] = ", ".join(draft.get("staffany_orgs") or [])
        if draft.get("ps_team"):
            values[_ps_team_field_id()] = draft["ps_team"]
        return values

    fields = _field_ids()
    values: dict[str, Any] = {
        "summary": draft["summary"],
        "description": _description_from_draft(draft),
    }
    mappings = {
        fields["customer"]: draft.get("customer"),
        fields["staffany_orgs"]: ", ".join(draft.get("staffany_orgs") or []),
        fields["owner_psm"]: draft.get("owner_psm"),
        fields["contributor_cse"]: draft.get("contributor_cse"),
        fields["action_type"]: draft.get("action_type"),
        fields["risk_reason"]: draft.get("risk_reason"),
        fields["source_links"]: "\n".join(draft.get("source_links") or []),
    }
    if draft.get("priority"):
        values["priority"] = {"name": draft["priority"]}
    for field_id, value in mappings.items():
        if value:
            values[field_id] = value
    return values


def _duplicate_candidates(customer: str, summary: str) -> list[dict[str, Any]]:
    terms = [term for term in [customer, summary] if term]
    if not terms:
        return []
    clauses = [f'text ~ {_quote_jql(term[:80])}' for term in terms[:2]]
    jql = f"project = {_project_key()} AND statusCategory != Done AND ({' OR '.join(clauses)}) ORDER BY updated DESC"
    try:
        return [_safe_issue(issue) for issue in _search_issues(jql, _search_fields(), 5)]
    except JiraError:
        return []


def _ticket_by_slack_thread(slack_thread_url: str, max_results: int = 5) -> list[dict[str, Any]]:
    source = (slack_thread_url or "").strip()
    if not source:
        return []
    jql = (
        f"project = {_project_key()} AND text ~ {_quote_jql(source[:180])} "
        "ORDER BY updated DESC"
    )
    return [_safe_issue(issue) for issue in _search_issues(jql, _search_fields(), max_results)]


def _search_fields() -> list[str]:
    fields = list(SAFE_FIELDS)
    reminder_field = _optional_field_id("reminder_at")
    if reminder_field:
        fields.append(reminder_field)
    return fields


@mcp.tool()
def validate_jira_configuration() -> dict[str, Any]:
    """Validate configured PCO Jira IDs, fields, request types, and caller policy path."""

    scope = {"project_key": _project_key()}
    missing = []
    required_env = [
        "JIRA_BASE_URL",
        "JIRA_EMAIL",
        "JIRA_API_TOKEN",
    ]
    if not _is_thin_poc():
        required_env.extend(
            [
                "PSM_OPS_JIRA_SERVICE_DESK_ID",
                "PSM_OPS_ACCESS_POLICY_PATH",
                *REQUEST_TYPE_ENVS.values(),
                *FIELD_ENVS.values(),
            ]
        )
    for env_name in required_env:
        if not _env(env_name):
            missing.append(env_name)
    if missing:
        return _blocked(f"Missing Jira config: {', '.join(missing)}", scope)

    try:
        _load_policy()
        field_payload = _request_json("GET", "/rest/api/3/field")
        field_ids = {field.get("id") for field in field_payload if isinstance(field, dict)}
        configured_fields = _configured_fields()
        missing_fields = [field for field in configured_fields.values() if field not in field_ids and field not in {"duedate", "priority"}]
        request_type_checks = {}
        for key in REQUEST_TYPE_ENVS:
            try:
                request_type_id = _request_type_id(key)
            except JiraError as error:
                if _is_thin_poc() and key == "handoff_package":
                    request_type_checks[key] = {"enabled": False, "reason": str(error)}
                    continue
                raise
            path = f"/rest/servicedeskapi/servicedesk/{_service_desk_id()}/requesttype/{request_type_id}/field"
            request_type_checks[key] = {"enabled": bool(_request_json("GET", path)), "id": request_type_id}
    except JiraError as error:
        return _blocked(str(error), scope)

    if missing_fields:
        return _blocked(f"Configured Jira field IDs not found: {', '.join(missing_fields)}", scope)

    return _verified(
        {
            "project_key": _project_key(),
            "mode": _jira_mode(),
            "service_desk_id": _service_desk_id(),
            "request_types": request_type_checks,
            "fields": configured_fields,
            "allowed_statuses": list(ALLOWED_STATUSES.values()),
        },
        scope,
    )


@mcp.tool()
def list_my_pco_tasks(
    slack_user_email: str,
    filter: str = "open",
    max_results: int = 25,
) -> dict[str, Any]:
    """List safe summaries for the caller's own PCO tasks."""

    scope = {"caller": (slack_user_email or "").strip().lower(), "filter": filter}
    try:
        caller = _caller(slack_user_email)
        account_id = caller["jira_account_id"]
        clauses = [f"project = {_project_key()}", f"assignee = {_quote_jql(account_id)}"]
        normalized_filter = (filter or "open").strip().lower()
        if normalized_filter in {"open", "active"}:
            clauses.append("statusCategory != Done")
        elif normalized_filter == "overdue":
            clauses.append("statusCategory != Done")
            clauses.append("duedate < now()")
        elif normalized_filter in {"due_this_week", "due this week"}:
            clauses.append("statusCategory != Done")
            clauses.append("duedate <= endOfWeek()")
        elif normalized_filter in {"done", "completed"}:
            clauses.append("statusCategory = Done")
        else:
            clauses.append("statusCategory != Done")
        jql = " AND ".join(clauses) + " ORDER BY duedate ASC, updated DESC"
        issues = _search_issues(jql, _search_fields(), max_results)
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified([_safe_issue(issue) for issue in issues], {**scope, "jira_account_id": caller["jira_account_id"]})


@mcp.tool()
def draft_pco_task(
    slack_user_email: str,
    customer: str,
    summary: str,
    due_date: str,
    action_type: str = "Customer success",
    priority: str = "Medium",
    risk_reason: str = "",
    source_links: list[str] | None = None,
    staffany_orgs: list[str] | None = None,
    contributor_cse: str = "",
    request_type_key: str = "customer_next_action",
) -> dict[str, Any]:
    """Build a Jira-ready PCO task draft without creating it."""

    scope = {"caller": (slack_user_email or "").strip().lower(), "customer": customer, "request_type_key": request_type_key}
    try:
        caller = _caller(slack_user_email)
        request_type_id = _request_type_id(request_type_key)
        _configured_fields()
    except JiraError as error:
        return _blocked(str(error), scope)

    if not customer or not summary:
        return _blocked("Customer and summary are required for a PCO task draft.", scope)

    draft = {
        "customer": customer.strip(),
        "summary": summary.strip(),
        "due_date": due_date.strip(),
        "action_type": (action_type or "Customer success").strip(),
        "priority": (priority or "Medium").strip(),
        "risk_reason": (risk_reason or "").strip(),
        "source_links": [str(link).strip() for link in (source_links or []) if str(link).strip()],
        "staffany_orgs": [str(org).strip() for org in (staffany_orgs or []) if str(org).strip()],
        "owner_psm": caller["display_name"],
        "owner_jira_account_id": caller["jira_account_id"],
        "contributor_cse": contributor_cse.strip(),
        "request_type_key": request_type_key,
        "request_type_id": request_type_id,
        "approval_required": True,
        "mode": _jira_mode(),
    }
    duplicates = _duplicate_candidates(draft["customer"], draft["summary"])
    return _verified(
        {"draft": draft, "duplicate_candidates": duplicates},
        {**scope, "jira_account_id": caller["jira_account_id"]},
        "Reply create to create this PCO task.",
    )


@mcp.tool()
def create_approved_pco_task(draft: dict[str, Any], approval_marker: str) -> dict[str, Any]:
    """Create a PCO JSM request from a previously reviewed draft."""

    marker = (approval_marker or "").strip().lower()
    scope = {"customer": draft.get("customer"), "request_type_key": draft.get("request_type_key")}
    if marker not in {"create", "approve create", "create this", "approved"}:
        return _blocked("Explicit same-thread create approval is required.", scope)

    return _create_pco_task_from_draft(draft, scope)


def _create_pco_task_from_draft(draft: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    """Create a PCO JSM request from an already-authorized draft."""

    try:
        request_type_id = str(draft.get("request_type_id") or _request_type_id(str(draft.get("request_type_key") or "customer_next_action")))
        request_values = _request_field_values(draft)
        payload = {
            "serviceDeskId": _service_desk_id(),
            "requestTypeId": request_type_id,
            "requestFieldValues": request_values,
            "isAdfRequest": False,
        }
        if not _is_thin_poc() and draft.get("owner_jira_account_id"):
            payload["raiseOnBehalfOf"] = draft.get("owner_jira_account_id")
        try:
            response = _request_json("POST", "/rest/servicedeskapi/request", payload)
            warnings: list[str] = []
        except JiraError:
            if not _is_thin_poc() or set(request_values) == {"summary"}:
                raise
            payload["requestFieldValues"] = {"summary": draft["summary"]}
            response = _request_json("POST", "/rest/servicedeskapi/request", payload)
            warnings = ["Optional PCO request fields were skipped because Jira rejected their values."]
    except JiraError as error:
        return _blocked(str(error), scope)

    issue_key = response.get("issueKey") or response.get("issueId") or response.get("key")
    if issue_key and draft.get("due_date"):
        try:
            _set_issue_due_date(str(issue_key), str(draft["due_date"]))
        except JiraError:
            warnings.append("Issue was created but due date could not be set.")
    if issue_key and draft.get("slack_thread_url"):
        metadata_comment = _metadata_comment_from_draft(draft)
        if metadata_comment:
            comment_result = add_internal_pco_comment(str(issue_key), metadata_comment)
            if comment_result.get("confidence") != "verified":
                warnings.append("Slack intake metadata internal comment could not be added.")
    if issue_key and _is_thin_poc():
        if not draft.get("slack_thread_url"):
            metadata_comment = _metadata_comment_from_draft(draft)
            comment_result = add_internal_pco_comment(str(issue_key), metadata_comment)
            if comment_result.get("confidence") != "verified":
                warnings.append("Metadata internal comment could not be added.")
        if draft.get("owner_jira_account_id"):
            try:
                _assign_issue(str(issue_key), str(draft["owner_jira_account_id"]))
            except JiraError:
                warnings.append("Issue was created but could not be assigned to the caller.")
    if issue_key and draft.get("add_needs_info_label"):
        try:
            _update_issue_labels(str(issue_key), add=["needs-info"])
        except JiraError:
            warnings.append("Issue was created but the needs-info label could not be set.")
    return _verified(
        {
            "issue_key": issue_key,
            "url": f"{_jira_base_url()}/browse/{issue_key}" if issue_key else "",
            "jira_response": {key: response.get(key) for key in ["issueId", "issueKey", "requestTypeId"] if key in response},
            "warnings": warnings,
        },
        scope,
    )


@mcp.tool()
def find_ticket_by_slack_thread(slack_thread_url: str, max_results: int = 5) -> dict[str, Any]:
    """Find existing PCO tickets that already cite a Slack thread permalink."""

    source = (slack_thread_url or "").strip()
    scope = {"slack_thread_url": source, "max_results": max(1, min(int(max_results or 5), 20))}
    if not source:
        return _blocked("Slack thread URL is required for ticket traceability.", scope)
    try:
        matches = _ticket_by_slack_thread(source, scope["max_results"])
    except JiraError as error:
        return _blocked(str(error), scope)
    return _verified(
        {"matches": matches},
        scope,
        "Same Slack thread permalink is the V1 ticket idempotency key.",
    )


@mcp.tool()
def create_ps_wee_intake_ticket(
    slack_user_email: str,
    slack_thread_url: str,
    customer: str = "",
    issue_summary: str = "",
    known_details: str = "",
    missing_info: list[str] | None = None,
    impact: str = "",
    affected_scope: str = "",
    expected_outcome: str = "",
    evidence_links: list[str] | None = None,
    priority: str = "Medium",
    due_date: str = "",
    request_type_key: str = "customer_next_action",
    ps_team: str = "PS WEE",
) -> dict[str, Any]:
    """Create an immediate PCO intake ticket for PS WEE/PSM Manager Ops requests."""

    source = (slack_thread_url or "").strip()
    normalized_customer = (customer or "").strip() or "Unknown customer"
    normalized_issue = (issue_summary or "").strip() or "PS request from Slack"
    scope = {
        "caller": (slack_user_email or "").strip().lower(),
        "slack_thread_url": source,
        "customer": normalized_customer,
        "request_type_key": request_type_key,
    }
    if not source:
        return _blocked("Slack thread URL is required before creating a traceable PS WEE ticket.", scope)

    try:
        existing = _ticket_by_slack_thread(source, 5)
        if existing:
            return _verified(
                {"existing_ticket": existing[0], "duplicate_candidates": existing},
                scope,
                "Existing PCO ticket found for the same Slack thread; update it instead of creating a duplicate.",
            )
        try:
            caller = _caller(slack_user_email)
        except JiraError:
            caller = {
                "jira_account_id": "",
                "display_name": (slack_user_email or "").strip() or "Unresolved Slack requester",
            }
        request_type_id = _request_type_id(request_type_key)
        _configured_fields()
    except JiraError as error:
        return _blocked(str(error), scope)

    default_missing = [
        "customer/org",
        "issue details",
        "impact/urgency",
        "affected outlet/user/date range",
        "expected outcome",
        "screenshots/logs if relevant",
    ]
    missing = [str(item).strip() for item in (missing_info or default_missing) if str(item).strip()]
    source_links = [source]
    source_links.extend(str(link).strip() for link in (evidence_links or []) if str(link).strip())
    draft = {
        "customer": normalized_customer,
        "summary": f"[Needs info] {normalized_customer} - {normalized_issue}",
        "due_date": due_date.strip(),
        "action_type": "PS WEE ticket intake",
        "priority": (priority or "Medium").strip(),
        "risk_reason": "Needs info from Slack thread",
        "source_links": source_links,
        "staffany_orgs": [],
        "ps_team": (ps_team or "PS WEE").strip(),
        "owner_psm": caller["display_name"],
        "owner_jira_account_id": caller.get("jira_account_id", ""),
        "contributor_cse": "",
        "request_type_key": request_type_key,
        "request_type_id": request_type_id,
        "approval_required": False,
        "mode": _jira_mode(),
        "slack_thread_url": source,
        "known_details": (known_details or "").strip(),
        "missing_info": missing,
        "impact": (impact or "").strip(),
        "affected_scope": (affected_scope or "").strip(),
        "expected_outcome": (expected_outcome or "").strip(),
        "add_needs_info_label": True,
    }
    result = _create_pco_task_from_draft(draft, scope)
    if result.get("confidence") != "verified":
        return result
    answer = result.get("answer", {})
    answer["missing_info"] = missing
    issue_key = str(answer.get("issue_key") or "").strip()
    issue_url = str(answer.get("url") or "").strip()
    ticket_ref = f"<{issue_url}|{issue_key}>" if issue_key and issue_url else issue_key or issue_url or "the ticket"
    answer["slack_reply"] = (
        f"Created first so this won't be missed: {ticket_ref}. "
        f"I still need: {', '.join(missing)}."
    )
    return result


def _metadata_comment_from_draft(draft: dict[str, Any]) -> str:
    metadata = [
        ("Customer", draft.get("customer")),
        ("Owner PSM", draft.get("owner_psm")),
        ("Contributor CSE", draft.get("contributor_cse")),
        ("Due date", draft.get("due_date")),
        ("Priority", draft.get("priority")),
        ("Action type", draft.get("action_type")),
        ("Risk reason", draft.get("risk_reason")),
        ("Source Slack thread", draft.get("slack_thread_url")),
        ("Known details", draft.get("known_details")),
        ("Impact", draft.get("impact")),
        ("Affected scope", draft.get("affected_scope")),
        ("Expected outcome", draft.get("expected_outcome")),
        ("Missing info", ", ".join(draft.get("missing_info") or [])),
        ("Source links", ", ".join(draft.get("source_links") or [])),
    ]
    lines = [f"{label}: {value}" for label, value in metadata if value]
    if not lines:
        return ""
    header = "PS WEE ticket intake from Slack:" if draft.get("slack_thread_url") else "PSM Ops metadata from Slack-approved task creation:"
    return header + "\n" + "\n".join(lines)


def _update_issue_labels(issue_key: str, add: list[str] | None = None, remove: list[str] | None = None) -> None:
    updates: list[dict[str, str]] = []
    updates.extend({"add": label} for label in (add or []) if label)
    updates.extend({"remove": label} for label in (remove or []) if label)
    if not updates:
        return
    _request_json(
        "PUT",
        f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}",
        {"update": {"labels": updates}},
    )


def _assign_issue(issue_key: str, account_id: str) -> None:
    _request_json(
        "PUT",
        f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/assignee",
        {"accountId": account_id},
    )


def _set_issue_due_date(issue_key: str, due_date: str) -> None:
    value = (due_date or "").strip()
    if not value:
        return
    _request_json(
        "PUT",
        f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}",
        {"fields": {"duedate": value}},
    )


@mcp.tool()
def transition_pco_task(
    issue_key: str,
    target_status: str,
    slack_user_email: str = "",
    comment: str = "",
) -> dict[str, Any]:
    """Transition a PCO issue to a configured target status."""

    key = (issue_key or "").strip().upper()
    normalized_target = (target_status or "").strip().lower()
    scope = {"issue_key": key, "target_status": target_status, "caller": (slack_user_email or "").strip().lower()}
    if normalized_target not in ALLOWED_STATUSES:
        return _blocked(f"Unsupported target status: {target_status}", scope)
    if not key:
        return _blocked("Issue key is required.", scope)

    try:
        transitions_payload = _request_json("GET", f"/rest/api/3/issue/{urllib.parse.quote(key)}/transitions")
        transitions = transitions_payload.get("transitions", [])
        target_labels = STATUS_TRANSITION_CANDIDATES.get(
            normalized_target,
            {ALLOWED_STATUSES[normalized_target].lower()},
        )
        selected = next(
            (
                transition
                for transition in transitions
                if str(transition.get("name", "")).strip().lower() in target_labels
                or str((transition.get("to") or {}).get("name", "")).strip().lower() in target_labels
            ),
            None,
        )
        if not selected:
            return _blocked(f"No Jira transition to {ALLOWED_STATUSES[normalized_target]} is available for {key}.", scope)
        body: dict[str, Any] = {"transition": {"id": selected["id"]}}
        if comment:
            body["update"] = {"comment": [{"add": {"body": _adf(comment)}}]}
        _request_json("POST", f"/rest/api/3/issue/{urllib.parse.quote(key)}/transitions", body)
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified({"issue_key": key, "status": ALLOWED_STATUSES[normalized_target]}, scope)


@mcp.tool()
def add_internal_pco_comment(
    issue_key: str,
    comment: str,
    slack_user_email: str = "",
    public_comment: bool = False,
) -> dict[str, Any]:
    """Add an internal JSM comment to a PCO issue."""

    key = (issue_key or "").strip().upper()
    scope = {"issue_key": key, "caller": (slack_user_email or "").strip().lower(), "public_comment": bool(public_comment)}
    if not key or not (comment or "").strip():
        return _blocked("Issue key and comment are required.", scope)
    if public_comment and _env("PSM_OPS_JIRA_PUBLIC_COMMENTS_ENABLED").lower() != "true":
        return _blocked("Public customer-visible comments are disabled for PSM Ops Bot.", scope)

    try:
        payload = {"body": comment.strip(), "public": bool(public_comment)}
        response = _request_json("POST", f"/rest/servicedeskapi/request/{urllib.parse.quote(key)}/comment", payload)
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified(
        {"issue_key": key, "comment_id": response.get("id"), "public": bool(public_comment)},
        scope,
        "Comment body is not echoed back to avoid raw comment leakage.",
    )


@mcp.tool()
def append_ps_wee_ticket_update(
    issue_key: str,
    slack_thread_url: str,
    update_summary: str,
    updated_fields: dict[str, Any] | None = None,
    evidence_links: list[str] | None = None,
    slack_user_email: str = "",
) -> dict[str, Any]:
    """Append a structured internal JSM comment for meaningful Slack discussion updates."""

    key = (issue_key or "").strip().upper()
    source = (slack_thread_url or "").strip()
    summary = (update_summary or "").strip()
    fields = updated_fields or {}
    links = [str(link).strip() for link in (evidence_links or []) if str(link).strip()]
    scope = {"issue_key": key, "slack_thread_url": source, "caller": (slack_user_email or "").strip().lower()}
    if not key or not source:
        return _blocked("Issue key and Slack thread URL are required for PS WEE ticket updates.", scope)
    if not summary and not fields and not links:
        return _blocked("A meaningful update summary, updated fields, or evidence link is required.", scope)

    lines = ["PS WEE Slack ticket update:", f"Source Slack thread: {source}"]
    if summary:
        lines.append(f"Summary: {summary}")
    if fields:
        lines.append("Updated fields:")
        for field, value in fields.items():
            if value:
                lines.append(f"- {field}: {value}")
    if links:
        lines.append("Evidence links:")
        lines.extend(f"- {link}" for link in links)
    return add_internal_pco_comment(key, "\n".join(lines), slack_user_email)


@mcp.tool()
def mark_ps_wee_ticket_ready(
    issue_key: str,
    slack_thread_url: str,
    ready_summary: str = "",
    slack_user_email: str = "",
) -> dict[str, Any]:
    """Mark a PS WEE intake ticket as ready for triage after required info is collected."""

    key = (issue_key or "").strip().upper()
    source = (slack_thread_url or "").strip()
    scope = {"issue_key": key, "slack_thread_url": source, "caller": (slack_user_email or "").strip().lower()}
    if not key or not source:
        return _blocked("Issue key and Slack thread URL are required to mark a PS WEE ticket ready.", scope)
    lines = [
        "PS WEE ticket ready for triage.",
        f"Source Slack thread: {source}",
    ]
    if ready_summary.strip():
        lines.append(f"Ready summary: {ready_summary.strip()}")
    comment_result = add_internal_pco_comment(key, "\n".join(lines), slack_user_email)
    if comment_result.get("confidence") != "verified":
        return comment_result
    warnings: list[str] = []
    try:
        _update_issue_labels(key, remove=["needs-info"])
    except JiraError:
        warnings.append("Ready comment was added but the needs-info label could not be removed.")
    answer = comment_result.get("answer", {})
    answer["ready_for_triage"] = True
    answer["warnings"] = warnings
    return _verified(answer, scope, "Ticket readiness is marked by internal comment and removal of needs-info label when Jira allows it.")


@mcp.tool()
def set_pco_reminder(
    issue_key: str,
    reminder_at: str,
    slack_user_email: str = "",
    note: str = "",
) -> dict[str, Any]:
    """Set the PCO issue due date used by automatic due-date reminders."""

    key = (issue_key or "").strip().upper()
    reminder = (reminder_at or "").strip()
    scope = {"issue_key": key, "reminder_at": reminder, "caller": (slack_user_email or "").strip().lower()}
    if not key or not reminder:
        return _blocked("Issue key and reminder_at are required.", scope)

    try:
        due_date = _date_part(reminder)
        _set_issue_due_date(key, due_date)
        if note:
            add_internal_pco_comment(key, f"Automatic due-date reminder updated: {note}", slack_user_email)
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified(
        {
            "issue_key": key,
            "due_date": due_date,
            "reminder_policy": "Automatic reminders include tasks due tomorrow, due today, and overdue until Done.",
        },
        scope,
    )


@mcp.tool()
def list_due_pco_reminders(
    slack_user_email: str = "",
    as_of: str = "",
    window_hours: int = 0,
    include_overdue: bool = True,
    lead_days: int = 1,
    max_results: int = 50,
) -> dict[str, Any]:
    """List PCO tasks due within the automatic reminder window."""

    now = as_of.strip() if as_of else datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    scope = {
        "caller": (slack_user_email or "").strip().lower() or "automation",
        "as_of": now,
        "window_hours": int(window_hours or 0),
        "include_overdue": bool(include_overdue),
        "lead_days": int(lead_days if lead_days is not None else 1),
    }
    try:
        upper_due_date = _reminder_upper_due_date(now, int(window_hours or 0), int(lead_days if lead_days is not None else 1))
        today = _date_part(now)
        clauses = [f"project = {_project_key()}", "statusCategory != Done", "duedate is not EMPTY"]
        if include_overdue:
            clauses.append(f'duedate <= "{upper_due_date}"')
        else:
            clauses.append(f'duedate >= "{today}"')
            clauses.append(f'duedate <= "{upper_due_date}"')
        if slack_user_email:
            caller = _caller(slack_user_email)
            clauses.append(f"assignee = {_quote_jql(caller['jira_account_id'])}")
        jql = " AND ".join(clauses) + " ORDER BY duedate ASC, updated DESC"
        issues = _search_issues(jql, SAFE_FIELDS, max_results)
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified(
        [_safe_issue(issue) for issue in issues],
        scope,
        "Automatic reminder window is due tomorrow, due today, and overdue until Done.",
    )


def _date_part(value: str) -> str:
    raw = (value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError as error:
        raise JiraError(f"Invalid date or timestamp: {value}") from error


def _reminder_upper_due_date(as_of: str, window_hours: int, lead_days: int) -> str:
    normalized = as_of.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise JiraError(f"Invalid as_of timestamp: {as_of}") from error
    if window_hours > 0:
        return (parsed + timedelta(hours=window_hours)).date().isoformat()
    return (parsed + timedelta(days=max(0, lead_days))).date().isoformat()


def _add_hours(value: str, hours: int) -> str:
    if hours <= 0:
        return ""
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise JiraError(f"Invalid as_of timestamp: {value}") from error
    return (parsed + timedelta(hours=hours)).replace(microsecond=0).isoformat()


def _adf(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


if __name__ == "__main__":
    mcp.run("stdio")
