#!/usr/bin/env python3
"""Jira PCO/ROI MCP adapter for PSM Ops Bot."""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env
from psm_slack_notifier import post_ps_wee_audit


load_profile_env()

mcp = FastMCP(
    "psm_jira",
    instructions=(
        "PCO and ROI Jira Service Management task adapter for PSM Ops Bot. "
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
ENGINEERING_LINK_TARGET_RE = re.compile(r"^(KER|SCHE)-\d+$", re.IGNORECASE)
PCO_ISSUE_RE = re.compile(r"^PCO-\d+$", re.IGNORECASE)
ISSUE_LINK_TYPE_ALIASES = {
    "blocks": "Blocks",
    "is blocked by": "Blocks",
    "blocked by": "Blocks",
    "relates": "Relates",
    "relates to": "Relates",
}

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

ROI_FIELD_ENVS = {
    "customer": "PSM_OPS_ROI_JIRA_FIELD_CUSTOMER",
    "staffany_orgs": "PSM_OPS_ROI_JIRA_FIELD_STAFFANY_ORGS",
    "request_category": "PSM_OPS_ROI_JIRA_FIELD_REQUEST_CATEGORY",
    "source_links": "PSM_OPS_ROI_JIRA_FIELD_SOURCE_LINKS",
    "requester": "PSM_OPS_ROI_JIRA_FIELD_REQUESTER",
    "requester_slack": "PSM_OPS_ROI_JIRA_FIELD_REQUESTER_SLACK",
    "original_channel": "PSM_OPS_ROI_JIRA_FIELD_ORIGINAL_CHANNEL",
    "priority": "PSM_OPS_ROI_JIRA_FIELD_PRIORITY",
}

ROI_TRIGGER_PATTERNS = [
    ("ROI", r"\broi\b"),
    ("RevOps", r"\brev\s*ops\b|\brevops\b"),
    ("BD Ops", r"\bbd\s*ops\b|\bbdops\b"),
    ("NYSS", r"\bnyss\b|\bn\s*y\s*s\s*s\b"),
    ("invoice", r"\binvoices?\b|\brenewal\s+invoices?\b|\bstripe\s+invoices?\b|\baccessible\s+invoices?\b"),
    ("billing", r"\bbilling\b"),
    ("discount", r"\bdiscounts?\b"),
    ("HC/deal check", r"\bhc\s*/?\s*deal\s+checks?\b|\bheadcount\s*/?\s*deal\s+checks?\b|\bdeal\s+checks?\b"),
    ("HubSpot deal", r"\bhubspot\s+deals?\b"),
    ("ERP dashboard/data issue", r"\berp\b|\bdashboards?\b|\bdata\s+issues?\b"),
    ("linked BE", r"\blink(?:ed)?\s+be\b|\bbusiness\s+entity\b"),
    ("MRR mismatch", r"\bmrr\s+mismatch(?:es)?\b"),
    ("SLA dashboard", r"\bsla\s+dashboards?\b"),
    ("asset sync", r"\basset\s+sync\b"),
]

ROI_ACTION_PATTERN = re.compile(
    r"\b(create|add|log|raise|file|handle|put|ticket|task|board)\b",
    re.IGNORECASE,
)
ROI_TRACKER_LABEL = "ps-wee-roi-tracker"
ROI_TRACKER_DEFAULT_TERMS = {
    "invoice",
    "billing",
    "discount",
    "HC/deal check",
    "HubSpot deal",
    "ERP dashboard/data issue",
    "linked BE",
    "MRR mismatch",
    "SLA dashboard",
    "asset sync",
}
ROI_TRACKING_REQUEST_PATTERN = re.compile(
    r"\b(track|tracking|follow[- ]?up|close\s+the\s+loop|customer\s+loop|pending\s+internal(?:\s+team)?)\b",
    re.IGNORECASE,
)
SENSITIVE_INFO_PATTERN = re.compile(
    r"\b(password|secret|token|api\s*key|credential)\b",
    re.IGNORECASE,
)

PS_TEAM_ALIASES = {
    "cs": "CS Duty",
    "cs duty": "CS Duty",
    "cs-duty": "CS Duty",
    "cs_duty": "CS Duty",
    "csduty": "CS Duty",
    "customer success duty": "CS Duty",
    "eng": "Eng Duty",
    "eng duty": "Eng Duty",
    "eng-duty": "Eng Duty",
    "eng_duty": "Eng Duty",
    "engduty": "Eng Duty",
    "engineering duty": "Eng Duty",
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

SLACK_USER_CACHE: list[dict[str, Any]] | None = None


class JiraError(RuntimeError):
    pass


@mcp.resource(
    "jira://request-types",
    name="PCO and ROI request types",
    description="Configured PCO/ROI request types and identity rules for PSM Ops Bot.",
    mime_type="application/json",
)
def jira_request_types_resource() -> str:
    """Expose safe request type metadata to prevent model-side guessing."""

    payload = {
        "project_key": _project_key(),
        "mode": _jira_mode(),
        "service_desk_id": _service_desk_id() if _env("PSM_OPS_JIRA_SERVICE_DESK_ID") or _is_thin_poc() else "",
        "request_types": {
            key: _request_type_id(key) if key != "handoff_package" or not _is_thin_poc() else "disabled_until_request_type_exists"
            for key in REQUEST_TYPE_ENVS
        },
        "fields": {
            "ps_team": _ps_team_field_id(),
            "staffany_orgs": _optional_field_id("staffany_orgs"),
            "due_date": "duedate",
        },
        "roi": {
            "project_key": _env("PSM_OPS_ROI_JIRA_PROJECT_KEY"),
            "service_desk_id": _env("PSM_OPS_ROI_JIRA_SERVICE_DESK_ID"),
            "request_type_id": _env("PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID"),
            "field_envs": ROI_FIELD_ENVS,
            "idempotency_key": "Slack thread permalink",
            "requester_rule": "Resolve explicit requested/reported-by first, else current Slack sender. Never fall back to bot/team identities.",
            "pco_tracker": {
                "label": ROI_TRACKER_LABEL,
                "default_for_ps_team_billing": True,
                "status": "Waiting Internal",
            },
        },
        "caller_identity": {
            "tool_parameter": "slack_user_email",
            "accepted_values": ["Slack sender user id", "Slack mention", "Slack profile email"],
            "rule": "Pass the current Slack sender id or mention when email is not already provided; do not ask the user for email.",
        },
    }
    return json.dumps(payload, sort_keys=True)
class CustomerChannelMapMiss(JiraError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _today_date() -> date:
    override = _env("PSM_OPS_TODAY")
    if override:
        try:
            return datetime.strptime(override, "%Y-%m-%d").date()
        except ValueError as error:
            raise JiraError("PSM_OPS_TODAY must be YYYY-MM-DD when configured.") from error
    timezone_name = _env("PSM_OPS_TIMEZONE", "Asia/Singapore") or "Asia/Singapore"
    try:
        local_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise JiraError("PSM_OPS_TIMEZONE must be a valid IANA timezone when configured.") from error
    return datetime.now(local_timezone).date()


def _validate_due_date_for_write(due_date: str) -> str:
    value = (due_date or "").strip()
    if not value:
        return ""
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as error:
        raise JiraError("Due date must be YYYY-MM-DD before creating a PCO task.") from error
    today = _today_date()
    if parsed < today:
        raise JiraError(f"Due date {value} is before today ({today.isoformat()}). Confirm a future due date before creating the PCO task.")
    return value


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


def _roi_project_key() -> str:
    value = _env("PSM_OPS_ROI_JIRA_PROJECT_KEY")
    if not value:
        raise JiraError("PSM_OPS_ROI_JIRA_PROJECT_KEY is not configured.")
    if "," in value:
        raise JiraError("PSM_OPS_ROI_JIRA_PROJECT_KEY must contain exactly one project key.")
    return value.upper()


def _roi_service_desk_id() -> str:
    value = _env("PSM_OPS_ROI_JIRA_SERVICE_DESK_ID")
    if not value:
        raise JiraError("PSM_OPS_ROI_JIRA_SERVICE_DESK_ID is not configured.")
    if "," in value:
        raise JiraError("PSM_OPS_ROI_JIRA_SERVICE_DESK_ID must contain exactly one service desk ID.")
    return value


def _roi_request_type_id() -> str:
    value = _env("PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID")
    if not value:
        raise JiraError("PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID is not configured.")
    if "," in value:
        raise JiraError("PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID must contain exactly one request type ID.")
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


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").strip().lower()).strip()


def _normalize_match_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _normalize_ps_team(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    normalized = _normalize_label(raw)
    if normalized in PS_TEAM_ALIASES:
        return PS_TEAM_ALIASES[normalized]
    return raw


def _infer_ps_team_from_text(*values: str) -> str:
    haystack = _normalize_label(" ".join(str(value or "") for value in values))
    if re.search(r"\bcs duty\b", haystack):
        return "CS Duty"
    if re.search(r"\beng duty\b", haystack):
        return "Eng Duty"
    return ""


def _ps_team_valid_values(request_type_id: str = "") -> list[dict[str, Any]]:
    try:
        rid = request_type_id or _request_type_id("data_hygiene")
        payload = _request_json(
            "GET",
            f"/rest/servicedeskapi/servicedesk/{urllib.parse.quote(_service_desk_id())}"
            f"/requesttype/{urllib.parse.quote(rid)}/field",
        )
    except JiraError:
        return []
    fields = payload.get("requestTypeFields", []) if isinstance(payload, dict) else []
    for field in fields:
        if not isinstance(field, dict):
            continue
        if field.get("fieldId") == _ps_team_field_id() or _normalize_label(str(field.get("name") or "")) == "ps team":
            values = field.get("validValues") or []
            return [value for value in values if isinstance(value, dict)]
    return []


def _ps_team_request_value(label: str, request_type_id: str = "") -> Any:
    normalized = _normalize_ps_team(label)
    if not normalized:
        return ""
    normalized_key = _normalize_label(normalized)
    for option in _ps_team_valid_values(request_type_id):
        if _normalize_label(str(option.get("label") or "")) == normalized_key:
            return option.get("value") or option.get("id") or normalized
    return normalized


def _ps_team_issue_value(label: str) -> Any:
    normalized = _normalize_ps_team(label)
    if not normalized:
        return ""
    normalized_key = _normalize_label(normalized)
    for option in _ps_team_valid_values():
        if _normalize_label(str(option.get("label") or "")) == normalized_key:
            option_id = str(option.get("value") or option.get("id") or "").strip()
            if option_id:
                return {"id": option_id}
    return {"value": normalized}


def _configured_roi_field_ids() -> dict[str, str]:
    return {
        key: _env(env_name)
        for key, env_name in ROI_FIELD_ENVS.items()
        if _env(env_name)
    }


def _roi_request_type_fields() -> list[dict[str, Any]]:
    payload = _request_json(
        "GET",
        f"/rest/servicedeskapi/servicedesk/{urllib.parse.quote(_roi_service_desk_id())}"
        f"/requesttype/{urllib.parse.quote(_roi_request_type_id())}/field",
    )
    fields = payload.get("requestTypeFields", []) if isinstance(payload, dict) else []
    return [field for field in fields if isinstance(field, dict)]


def _roi_field_required(field: dict[str, Any]) -> bool:
    return bool(field.get("required"))


def _roi_field_name(field: dict[str, Any]) -> str:
    return str(field.get("name") or field.get("fieldId") or "").strip()


def _roi_field_key(field: dict[str, Any]) -> str:
    field_id = str(field.get("fieldId") or "").strip()
    configured = _configured_roi_field_ids()
    for key, configured_id in configured.items():
        if configured_id and configured_id == field_id:
            return key
    name = _normalize_label(_roi_field_name(field))
    if field_id == "summary" or name in {"summary", "title"} or "summary" in name or "title" in name:
        return "summary"
    if field_id == "description" or "description" in name or "details" in name or "context" in name:
        return "details"
    if "staffany" in name and any(token in name for token in ["org", "organisation", "organization"]):
        return "staffany_orgs"
    if name == "org" or any(token in name for token in ["company", "customer", "account", " org ", "organisation", "organization"]):
        return "customer"
    if "requester" in name or "requestor" in name or ("reported" in name and "by" in name) or ("requested" in name and "by" in name):
        return "requester"
    if "category" in name or ("request" in name and "type" in name):
        return "request_category"
    if "channel" in name:
        return "original_channel"
    if "source" in name or "slack" in name or "thread" in name or "link" in name or "evidence" in name:
        return "source_links"
    if "priority" in name or "urgency" in name:
        return "priority"
    return ""


def _roi_field_mapping(fields: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    mapping: dict[str, dict[str, Any]] = {}
    ambiguous: list[str] = []
    configured_ids = _configured_roi_field_ids()
    configured_by_key = {key: field_id for key, field_id in configured_ids.items() if field_id}
    for field in fields:
        key = _roi_field_key(field)
        if not key:
            continue
        field_id = str(field.get("fieldId") or "")
        if key in mapping and str(mapping[key].get("fieldId") or "") != field_id:
            configured_field_id = configured_by_key.get(key)
            if configured_field_id == field_id:
                mapping[key] = field
                continue
            if configured_field_id == str(mapping[key].get("fieldId") or ""):
                continue
            if _roi_field_required(field) or _roi_field_required(mapping[key]):
                ambiguous.append(key)
            continue
        mapping[key] = field
    return mapping, sorted(set(ambiguous))


def _roi_option_value(field: dict[str, Any], raw_value: str) -> Any:
    value = (raw_value or "").strip()
    if not value:
        return ""
    options = [option for option in (field.get("validValues") or []) if isinstance(option, dict)]
    if not options:
        return value
    normalized = _normalize_label(value)
    for option in options:
        candidates = [
            str(option.get("label") or ""),
            str(option.get("name") or ""),
            str(option.get("value") or ""),
            str(option.get("id") or ""),
        ]
        if any(_normalize_label(candidate) == normalized for candidate in candidates if candidate):
            option_id = str(option.get("value") or option.get("id") or "").strip()
            if option_id:
                return {"id": option_id}
            option_name = str(option.get("label") or option.get("name") or "").strip()
            return {"name": option_name} if option_name else value
    return value


def _roi_default_priority_for_field(field: dict[str, Any]) -> str:
    options = [option for option in (field.get("validValues") or []) if isinstance(option, dict)]
    if not options:
        return "Medium"
    field_label = _normalize_label(_roi_field_name(field))
    if "urgent" in field_label:
        for option in options:
            labels = [
                str(option.get("label") or ""),
                str(option.get("name") or ""),
                str(option.get("value") or ""),
            ]
            if any(_normalize_label(label) == "no" for label in labels if label):
                return str(option.get("label") or option.get("name") or option.get("value") or "No")
    for preferred in ["medium", "normal"]:
        for option in options:
            labels = [
                str(option.get("label") or ""),
                str(option.get("name") or ""),
                str(option.get("value") or ""),
            ]
            if any(_normalize_label(label) == preferred for label in labels if label):
                return str(option.get("label") or option.get("name") or option.get("value") or preferred.title())
    return ""


def _configured_fields() -> dict[str, str]:
    if _is_thin_poc():
        return {
            "staffany_orgs": _field_id("staffany_orgs"),
            "ps_team": _ps_team_field_id(),
        }
    return _field_ids()


def _issue_url(issue_key: str) -> str:
    key = (issue_key or "").strip().upper()
    return f"{_jira_base_url()}/browse/{key}" if key else ""


def _notify_ps_wee_blocked(message: str, scope: dict[str, Any]) -> None:
    source = str((scope or {}).get("slack_thread_url") or "").strip()
    if not source:
        return
    key = str((scope or {}).get("issue_key") or "").strip().upper()
    try:
        issue_url = _issue_url(key)
    except JiraError:
        issue_url = ""
    try:
        post_ps_wee_audit(
            "blocked",
            source_thread_url=source,
            issue_key=key,
            issue_url=issue_url,
            requester=str((scope or {}).get("caller") or ""),
            customer=str((scope or {}).get("customer") or ""),
            blocked_reason=message,
            jira_payload={"scope": scope},
            extra={"subsystem": str((scope or {}).get("subsystem") or "jira_pco")},
        )
    except Exception:
        return


def _blocked(message: str, scope: dict[str, Any], source: str = "Jira PCO") -> dict[str, Any]:
    _notify_ps_wee_blocked(message, scope)
    return {
        "answer": {"status": "blocked", "message": message},
        "source": source,
        "scope": scope,
        "confidence": "blocked",
        "caveat": message,
    }


def _verified(answer: Any, scope: dict[str, Any], caveat: str = "None.", source: str = "Jira PCO") -> dict[str, Any]:
    return {
        "answer": answer,
        "source": source,
        "scope": scope,
        "confidence": "verified",
        "caveat": caveat,
    }


def _slack_channel_id_from_permalink(slack_thread_url: str) -> str:
    match = re.search(r"/archives/([A-Z0-9]+)/", slack_thread_url or "")
    return match.group(1) if match else ""


def _customer_channel_map_path() -> str:
    return _env("PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH")


def _load_customer_channel_map() -> list[dict[str, Any]]:
    path = _customer_channel_map_path()
    if not path:
        return []
    map_path = Path(path)
    if not map_path.exists():
        raise JiraError("PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH points to a missing file.")
    try:
        payload = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise JiraError("Customer channel map could not be read as JSON.") from error

    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("channels") or payload.get("mappings") or []
    else:
        raise JiraError("Customer channel map must be a list or an object with channels.")
    if not isinstance(entries, list):
        raise JiraError("Customer channel map channels must be a list.")
    return [entry for entry in entries if isinstance(entry, dict)]


def _customer_matches_mapping(customer: str, mapping: dict[str, Any]) -> bool:
    supplied = _normalize_match_key(customer)
    if not supplied:
        return True
    candidates = [
        _normalize_match_key(str(mapping.get("customer_name") or "")),
        _normalize_match_key(str(mapping.get("customer_key") or "")),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        if supplied == candidate:
            return True
        if len(supplied) >= 4 and supplied in candidate:
            return True
        if len(candidate) >= 4 and candidate in supplied:
            return True
    return False


def _reviewed_customer_channel_mapping(slack_thread_url: str, customer: str = "") -> dict[str, Any]:
    channel_id = _slack_channel_id_from_permalink(slack_thread_url)
    if not channel_id:
        raise JiraError("Slack thread URL must include a channel ID for customer-channel resolution.")

    matches = [
        entry
        for entry in _load_customer_channel_map()
        if str(entry.get("channel_id") or "").strip() == channel_id
    ]
    if not matches:
        raise CustomerChannelMapMiss(f"No reviewed customer-channel mapping found for Slack channel {channel_id}.")

    mapping = matches[0]
    required = ["channel_id", "channel_name", "customer_key", "customer_name", "staffany_orgs", "status"]
    missing = [key for key in required if not mapping.get(key)]
    if missing:
        raise JiraError(f"Customer-channel mapping for {channel_id} is incomplete: {', '.join(missing)}.")
    if str(mapping.get("status") or "").strip().lower() != "reviewed":
        raise JiraError(f"Customer-channel mapping for {channel_id} is not reviewed.")
    if not _customer_matches_mapping(customer, mapping):
        mapped = str(mapping.get("customer_name") or mapping.get("customer_key") or "").strip()
        raise JiraError(f"Slack channel maps to {mapped}, but request named {customer.strip()}. Confirm the customer before creating the ticket.")

    orgs = mapping.get("staffany_orgs")
    if isinstance(orgs, str):
        org_list = [org.strip() for org in orgs.split(",") if org.strip()]
    elif isinstance(orgs, list):
        org_list = [str(org).strip() for org in orgs if str(org).strip()]
    else:
        org_list = []
    if not org_list:
        raise JiraError(f"Customer-channel mapping for {channel_id} has no StaffAny org values.")

    return {
        "channel_id": channel_id,
        "channel_name": str(mapping.get("channel_name") or "").strip(),
        "customer_key": str(mapping.get("customer_key") or "").strip(),
        "customer_name": str(mapping.get("customer_name") or "").strip(),
        "staffany_orgs": org_list,
        "status": str(mapping.get("status") or "").strip(),
    }


@mcp.tool()
def resolve_customer_channel_org(slack_thread_url: str, customer: str = "") -> dict[str, Any]:
    """Resolve a reviewed Slack customer channel mapping to Customer 360 customer and StaffAny orgs."""

    source = (slack_thread_url or "").strip()
    supplied_customer = (customer or "").strip()
    scope = {
        "slack_thread_url": source,
        "channel_id": _slack_channel_id_from_permalink(source),
        "customer": supplied_customer,
    }
    if not source:
        return _blocked("Slack thread URL is required for customer-channel resolution.", scope)
    try:
        mapping = _reviewed_customer_channel_mapping(source, supplied_customer)
    except JiraError as error:
        return _blocked(str(error), scope)
    return _verified(
        mapping,
        {**scope, "channel_id": mapping["channel_id"]},
        "Only reviewed Slack channel mappings can auto-tag PCO tickets.",
    )


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


def _issue_link_exists_between(issue_key: str, linked_issue_key: str, link_type: str) -> bool:
    payload = _request_json(
        "GET",
        f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}?fields=issuelinks",
    )
    issue_links = ((payload.get("fields") or {}).get("issuelinks") or [])
    for issue_link in issue_links:
        if ((issue_link.get("type") or {}).get("name") or "") != link_type:
            continue
        inward_key = ((issue_link.get("inwardIssue") or {}).get("key") or "").upper()
        outward_key = ((issue_link.get("outwardIssue") or {}).get("key") or "").upper()
        if linked_issue_key in {inward_key, outward_key}:
            return True
    return False


def _issue_link_exists(pco_key: str, engineering_key: str, link_type: str) -> bool:
    return _issue_link_exists_between(pco_key, engineering_key, link_type)


def _looks_like_existing_issue_link_error(error: JiraError) -> bool:
    message = str(error).lower()
    return (
        ("issue link" in message or "link between" in message or "link" in message)
        and ("already exists" in message or "exists" in message or "duplicate" in message)
    )


def _slack_token() -> str:
    return _env("SLACK_BOT_TOKEN")


def _request_slack_json(method: str, params: dict[str, str]) -> Any:
    token = _slack_token()
    if not token:
        raise JiraError("SLACK_BOT_TOKEN is not configured for Slack user matching.")
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://slack.com/api/{method}?{query}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:400]
        raise JiraError(f"Slack API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise JiraError(f"Slack API unavailable: {error.reason}") from error
    if not payload.get("ok"):
        raise JiraError(f"Slack API failed: {payload.get('error', 'unknown_error')}")
    return payload


def _slack_users() -> list[dict[str, Any]]:
    global SLACK_USER_CACHE
    if SLACK_USER_CACHE is not None:
        return SLACK_USER_CACHE
    users: list[dict[str, Any]] = []
    cursor = ""
    while True:
        params = {"limit": "200"}
        if cursor:
            params["cursor"] = cursor
        payload = _request_slack_json("users.list", params)
        for user in payload.get("members", []):
            if not isinstance(user, dict):
                continue
            if user.get("deleted") or user.get("is_bot"):
                continue
            users.append(user)
        cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "")
        if not cursor:
            break
    SLACK_USER_CACHE = users
    return users


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


def _identity_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())


def _email_local_key(value: str) -> str:
    email = _normalize_slack_email(value)
    if "@" not in email:
        return ""
    return _identity_key(email.split("@", 1)[0])


def _slack_user_email(user: dict[str, Any]) -> str:
    profile = user.get("profile") or {}
    return str(profile.get("email") or "").strip().lower()


def _slack_user_identity_keys(user: dict[str, Any]) -> set[str]:
    profile = user.get("profile") or {}
    values = [
        user.get("name"),
        user.get("real_name"),
        profile.get("real_name"),
        profile.get("display_name"),
        _slack_user_email(user),
        _email_local_key(_slack_user_email(user)),
    ]
    return {_identity_key(str(value)) for value in values if _identity_key(str(value))}


def _resolve_slack_user(value: str) -> dict[str, Any] | None:
    raw = value or ""
    mention = re.search(r"<@([A-Z0-9]+)>", raw)
    user_id = mention.group(1) if mention else raw.strip()
    email = _normalize_slack_email(raw)
    input_keys = {
        _identity_key(raw),
        _identity_key(email),
        _email_local_key(email),
    }
    input_keys = {key for key in input_keys if key}
    if not input_keys:
        return None
    try:
        users = _slack_users()
    except JiraError:
        return None
    if user_id:
        for user in users:
            if str(user.get("id") or "").strip() == user_id:
                return user
    exact_email = email if "@" in email else ""
    if exact_email:
        for user in users:
            if _slack_user_email(user) == exact_email:
                return user
    matches = [user for user in users if input_keys & _slack_user_identity_keys(user)]
    return matches[0] if len(matches) == 1 else None


@mcp.tool()
def resolve_slack_user_identity(value: str) -> dict[str, Any]:
    """Resolve one Slack mention/name/email to safe identity fields using the bot token."""

    raw = (value or "").strip()
    scope = {"query": raw}
    if not raw:
        return _blocked("Slack user mention, name, or email is required.", scope)
    try:
        user = _resolve_slack_user(raw)
    except JiraError as error:
        return _blocked(str(error), scope)
    if not user:
        return _blocked("No unique Slack user matched the supplied value.", scope)
    profile = user.get("profile") or {}
    return {
        "answer": {
            "slack_user_id": str(user.get("id") or ""),
            "slack_name": str(user.get("name") or ""),
            "real_name": str(user.get("real_name") or profile.get("real_name") or "").strip(),
            "display_name": str(profile.get("display_name") or "").strip(),
            "email": _slack_user_email(user),
            "is_bot": bool(user.get("is_bot")),
        },
        "source": "Slack users.list",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Single-user safe identity fields only; no bulk Slack export.",
    }


def _ps_team_options() -> list[dict[str, str]]:
    field_id = _ps_team_field_id()
    contexts = _request_json("GET", f"/rest/api/3/field/{field_id}/context")
    options: list[dict[str, str]] = []
    for context in contexts.get("values", []) if isinstance(contexts, dict) else []:
        context_id = context.get("id")
        if not context_id:
            continue
        start_at = 0
        while True:
            payload = _request_json(
                "GET",
                f"/rest/api/3/field/{field_id}/context/{context_id}/option?startAt={start_at}&maxResults=100",
            )
            values = payload.get("values", []) if isinstance(payload, dict) else []
            for option in values:
                if not isinstance(option, dict) or option.get("disabled"):
                    continue
                value = str(option.get("value") or "").strip()
                if value:
                    options.append({"id": str(option.get("id") or ""), "value": value})
            if not values or payload.get("isLast", True):
                break
            start_at += len(values)
    return options


def _ps_team_option_for_identity(identity: dict[str, Any]) -> dict[str, str] | None:
    options = _ps_team_options()
    user = identity.get("slack_user") if isinstance(identity.get("slack_user"), dict) else None
    keys = {
        _identity_key(str(identity.get("slack_email") or "")),
        _email_local_key(str(identity.get("slack_email") or "")),
        _identity_key(str(identity.get("display_name") or "")),
    }
    if user:
        keys.update(_slack_user_identity_keys(user))
    keys = {key for key in keys if key}
    for option in options:
        option_key = _identity_key(option["value"])
        if option_key in keys:
            return option
    for option in options:
        option_key = _identity_key(option["value"])
        if len(option_key) >= 4 and any(key.startswith(option_key) or option_key in key for key in keys):
            return option
    return None


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


def _caller(slack_user_email: str, require_jira_account: bool = True, require_ps_team: bool = False) -> dict[str, Any]:
    supplied_email = _normalize_slack_email(slack_user_email)
    slack_user = _resolve_slack_user(slack_user_email)
    email = _slack_user_email(slack_user) if slack_user else supplied_email
    jira_email = _jira_email_for_slack(email)
    if not email:
        raise JiraError("Caller Slack email is required.")
    policy = _load_policy()
    for user in policy.get("users", []):
        if str(user.get("slack_email", "")).strip().lower() == email and user.get("active", True):
            account_id = str(user.get("jira_account_id", "")).strip()
            ps_team = str(user.get("ps_team") or user.get("ps_team_value") or "").strip()
            if require_jira_account and not account_id:
                raise JiraError(f"Jira account ID is missing for {email}.")
            if require_ps_team and not ps_team:
                raise JiraError(f"PS Team is missing for {email}.")
            return {
                "slack_email": email,
                "jira_account_id": account_id,
                "display_name": user.get("display_name") or email,
                "ps_team": ps_team,
                "ps_team_option_id": user.get("ps_team_option_id") or "",
            }
    if _is_thin_poc():
        caller: dict[str, Any] = {
            "slack_email": email,
            "jira_email": jira_email,
            "jira_account_id": "",
            "display_name": email,
            "slack_user": slack_user,
        }
        if slack_user:
            profile = slack_user.get("profile") or {}
            caller["display_name"] = (
                str(profile.get("real_name") or "").strip()
                or str(slack_user.get("real_name") or "").strip()
                or str(profile.get("display_name") or "").strip()
                or email
            )
        try:
            jira_user = _jira_user_by_email(jira_email)
            caller.update(jira_user)
            caller["slack_email"] = email
        except JiraError:
            if require_jira_account:
                raise
        caller["jira_email"] = jira_email
        ps_team_option = _ps_team_option_for_identity(caller)
        if ps_team_option:
            caller["ps_team"] = ps_team_option["value"]
            caller["ps_team_option_id"] = ps_team_option["id"]
        elif require_ps_team:
            raise JiraError(f"No PS Team option matched Slack user {email}.")
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


def _jira_assignable_user_for_issue(issue_key: str, assignee: str) -> dict[str, Any]:
    raw = (assignee or "").strip()
    key = (issue_key or "").strip().upper()
    if not key:
        raise JiraError("Issue key is required.")
    if not raw:
        raise JiraError("Assignee is required.")
    slack_user = _resolve_slack_user(raw)
    profile = slack_user.get("profile") if isinstance(slack_user, dict) else {}
    query_values = [
        _slack_user_email(slack_user) if slack_user else "",
        _normalize_slack_email(raw) if "@" in _normalize_slack_email(raw) else "",
        str(profile.get("real_name") or "").strip() if isinstance(profile, dict) else "",
        str(slack_user.get("real_name") or "").strip() if isinstance(slack_user, dict) else "",
        str(profile.get("display_name") or "").strip() if isinstance(profile, dict) else "",
        raw,
    ]
    seen: set[str] = set()
    for query_value in [value for value in query_values if value]:
        normalized_query = _identity_key(query_value)
        if normalized_query in seen:
            continue
        seen.add(normalized_query)
        query = urllib.parse.urlencode({"issueKey": key, "query": query_value, "maxResults": "10"})
        payload = _request_json("GET", f"/rest/api/3/user/assignable/search?{query}")
        users = [user for user in payload if isinstance(user, dict) and user.get("active", True)] if isinstance(payload, list) else []
        exact = [
            user
            for user in users
            if _identity_key(str(user.get("displayName") or "")) == normalized_query
            or _identity_key(str(user.get("emailAddress") or "")) == normalized_query
            or _email_local_key(str(user.get("emailAddress") or "")) == normalized_query
        ]
        selected = exact[0] if len(exact) == 1 else users[0] if len(users) == 1 else None
        if selected and selected.get("accountId"):
            return {
                "slack_email": str(selected.get("emailAddress") or "").strip().lower(),
                "jira_account_id": str(selected["accountId"]),
                "display_name": selected.get("displayName") or query_value,
            }
        if len(users) > 1:
            raise JiraError(f"No unique assignable Jira user found for assignee {raw} on {key}.")
    raise JiraError(f"No assignable Jira user found for assignee {raw} on {key}.")


def _quote_jql(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _normalize_issue_key(value: str) -> str:
    return (value or "").strip().upper()


def _normalize_issue_link_type(value: str) -> str:
    normalized = _normalize_label(value or "Blocks")
    return ISSUE_LINK_TYPE_ALIASES.get(normalized, "")


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
    ps_team = fields.get(_ps_team_field_id()) or {}
    return {
        "issue_key": issue.get("key", ""),
        "url": f"{_jira_base_url()}/browse/{issue.get('key', '')}",
        "summary": fields.get("summary") or issue.get("key", ""),
        "status": (fields.get("status") or {}).get("name", "Not set"),
        "priority": (fields.get("priority") or {}).get("name", "Not set"),
        "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
        "ps_team": ps_team.get("value", "Not set") if isinstance(ps_team, dict) else (ps_team or "Not set"),
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
            values[_ps_team_field_id()] = _ps_team_request_value(str(draft["ps_team"]), str(draft.get("request_type_id") or ""))
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
    if draft.get("ps_team"):
        values[_ps_team_field_id()] = _ps_team_request_value(str(draft["ps_team"]), str(draft.get("request_type_id") or ""))
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


def _pco_roi_tracker_by_slack_thread(slack_thread_url: str, max_results: int = 5) -> list[dict[str, Any]]:
    source = (slack_thread_url or "").strip()
    if not source:
        return []
    jql = (
        f"project = {_project_key()} "
        f"AND labels = {_quote_jql(ROI_TRACKER_LABEL)} "
        f"AND text ~ {_quote_jql(source[:180])} "
        "ORDER BY updated DESC"
    )
    return [_safe_issue(issue) for issue in _search_issues(jql, _search_fields(), max_results)]


def _safe_roi_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    return {
        "issue_key": issue.get("key", ""),
        "url": f"{_jira_base_url()}/browse/{issue.get('key', '')}",
        "summary": fields.get("summary") or issue.get("key", ""),
        "status": (fields.get("status") or {}).get("name", "Not set"),
        "priority": (fields.get("priority") or {}).get("name", "Not set"),
        "reporter": (fields.get("reporter") or {}).get("displayName", "Not set"),
        "created": fields.get("created") or "",
        "updated": fields.get("updated") or "",
        "request_type": (fields.get("issuetype") or {}).get("name", "Not set"),
    }


def _roi_ticket_by_slack_thread(slack_thread_url: str, max_results: int = 5) -> list[dict[str, Any]]:
    source = (slack_thread_url or "").strip()
    if not source:
        return []
    jql = (
        f"project = {_roi_project_key()} AND text ~ {_quote_jql(source[:180])} "
        "ORDER BY updated DESC"
    )
    return [_safe_roi_issue(issue) for issue in _search_issues(jql, list(SAFE_FIELDS), max_results)]


def _search_fields() -> list[str]:
    fields = list(SAFE_FIELDS)
    fields.append(_ps_team_field_id())
    reminder_field = _optional_field_id("reminder_at")
    if reminder_field:
        fields.append(reminder_field)
    return fields


def _detect_roi_ticket_request(message_text: str) -> dict[str, Any]:
    text = (message_text or "").strip()
    matched_terms = [
        label
        for label, pattern in ROI_TRIGGER_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    has_action = bool(ROI_ACTION_PATTERN.search(text))
    billing_tracker_terms = sorted(set(matched_terms) & ROI_TRACKER_DEFAULT_TERMS)
    has_tracker_default = bool(billing_tracker_terms and not SENSITIVE_INFO_PATTERN.search(text))
    tracking_requested = bool(ROI_TRACKING_REQUEST_PATTERN.search(text))
    should_track_pco = has_tracker_default or tracking_requested
    is_request = bool(matched_terms and (has_action or should_track_pco))
    caveat = "Actionable ROI/RevOps/BD Ops request." if is_request else "No ROI ticket should be created."
    if matched_terms and not has_action and not should_track_pco:
        caveat = "ROI/RevOps/BD Ops term found, but no create/add/log/handle/task action was requested."
    if has_tracker_default:
        caveat = "PS Team billing/ROI operational ask should create or reuse ROI and add a PCO customer-loop tracker."
    return {
        "is_roi_ticket_request": is_request,
        "matched_terms": sorted(set(matched_terms)),
        "requires_action": not has_tracker_default,
        "action_detected": has_action,
        "pco_tracker_default": bool(is_request and should_track_pco),
        "pco_tracker_reason": "billing_or_invoice_default" if has_tracker_default else ("explicit_tracking_request" if tracking_requested else ""),
        "tracking_requested": tracking_requested,
        "caveat": caveat,
    }


def _explicit_requester_from_text(message_text: str) -> str:
    text = message_text or ""
    patterns = [
        r"\b(?:requested|reported)\s+by\s+([^,\n;]+)",
        r"\b(?:requester|reporter)\s*[:=]\s*([^,\n;]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        candidate = match.group(1).strip()
        candidate = re.sub(r"\s+(?:for|to|about|because|re)\b.*$", "", candidate, flags=re.IGNORECASE).strip()
        if candidate:
            return candidate
    return ""


def _resolve_roi_requester(slack_user_email: str, requester: str, message_text: str) -> tuple[dict[str, Any], str, str]:
    explicit = (requester or "").strip() or _explicit_requester_from_text(message_text)
    source = "explicit_requester" if explicit else "slack_sender"
    query = explicit or (slack_user_email or "").strip()
    if not query:
        raise JiraError("Requester is required. Pass the current Slack sender or an explicit requested/reported-by user.")
    caller = _caller(query, require_jira_account=True, require_ps_team=False)
    if not caller.get("jira_account_id"):
        raise JiraError(f"Requester could not be resolved to a Jira account: {query}")
    return caller, source, query


def _infer_roi_category(*values: str) -> str:
    text = " ".join(str(value or "") for value in values)
    if re.search(r"\bbd\s*ops\b|\bbdops\b", text, flags=re.IGNORECASE):
        return "BD Ops"
    if re.search(r"\bnyss\b|\bn\s*y\s*s\s*s\b", text, flags=re.IGNORECASE):
        return "NYSS"
    if re.search(r"\brev\s*ops\b|\brevops\b", text, flags=re.IGNORECASE):
        return "RevOps"
    if re.search(r"\broi\b", text, flags=re.IGNORECASE):
        return "ROI"
    if re.search(r"\binvoices?\b|\bbilling\b|\bstripe\b", text, flags=re.IGNORECASE):
        return "Billing / invoice"
    return "RevOps"


def _compact_roi_summary(summary: str, message_text: str, customer: str) -> str:
    raw = (summary or "").strip()
    if raw:
        return raw[:160]
    cleaned = re.sub(r"\s+", " ", (message_text or "").strip())
    if cleaned:
        return cleaned[:160]
    if customer:
        return f"ROI request for {customer}"[:160]
    return "ROI request from Slack"


def _roi_requester_text(requester: dict[str, Any]) -> str:
    display = str(requester.get("display_name") or "").strip()
    email = str(requester.get("slack_email") or requester.get("jira_email") or "").strip()
    account_id = str(requester.get("jira_account_id") or "").strip()
    pieces = [piece for piece in [display, email, account_id] if piece]
    return " / ".join(pieces)


def _roi_metadata_comment(draft: dict[str, Any]) -> str:
    metadata = [
        ("Source Slack thread", draft.get("slack_thread_url")),
        ("Original channel", draft.get("original_channel")),
        ("Requester", draft.get("requester_text")),
        ("Requester source", draft.get("requester_source")),
        ("Customer/org", draft.get("customer")),
        ("StaffAny Organization", ", ".join(draft.get("staffany_orgs") or [])),
        ("Request category", draft.get("request_category")),
        ("Priority/urgency", draft.get("priority")),
        ("Summary", draft.get("summary")),
        ("Details", draft.get("details")),
        ("Evidence links", ", ".join(draft.get("evidence_links") or [])),
    ]
    lines = [f"{label}: {value}" for label, value in metadata if value]
    return "PS WEE ROI ticket intake from Slack:\n" + "\n".join(lines)


def _add_internal_jsm_comment(issue_key: str, comment: str) -> None:
    key = (issue_key or "").strip().upper()
    if not key or not comment.strip():
        return
    _request_json(
        "POST",
        f"/rest/servicedeskapi/request/{urllib.parse.quote(key)}/comment",
        {"body": comment.strip(), "public": False},
    )


def _roi_request_field_values(fields: list[dict[str, Any]], draft: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    mapping, ambiguous = _roi_field_mapping(fields)
    if ambiguous:
        raise JiraError(f"Ambiguous ROI request field mapping: {', '.join(ambiguous)}")

    field_values = {
        "summary": draft.get("summary", ""),
        "details": draft.get("description", ""),
        "customer": draft.get("customer", ""),
        "staffany_orgs": ", ".join(draft.get("staffany_orgs") or []),
        "request_category": draft.get("request_category", ""),
        "source_links": "\n".join([draft.get("slack_thread_url", ""), *(draft.get("evidence_links") or [])]).strip(),
        "requester": draft.get("requester_text", ""),
        "requester_slack": draft.get("requester_slack", ""),
        "original_channel": draft.get("original_channel", ""),
        "priority": draft.get("priority", ""),
    }
    values: dict[str, Any] = {}
    missing_required: list[str] = []

    for field in fields:
        field_id = str(field.get("fieldId") or "").strip()
        if not field_id:
            continue
        key = _roi_field_key(field)
        if not key:
            if _roi_field_required(field):
                missing_required.append(_roi_field_name(field))
            continue
        mapped_field = mapping.get(key)
        if mapped_field and str(mapped_field.get("fieldId") or "") != field_id:
            if _roi_field_required(field):
                missing_required.append(_roi_field_name(field))
            continue
        raw_value = str(field_values.get(key) or "").strip()
        if key == "priority" and not raw_value:
            raw_value = _roi_default_priority_for_field(field) if _roi_field_required(field) else ""
        if _roi_field_required(field) and not raw_value:
            missing_required.append(_roi_field_name(field))
            continue
        if raw_value:
            values[field_id] = _roi_option_value(field, raw_value)

    return values, sorted(set(missing_required))


@mcp.tool()
def classify_roi_ticket_request(message_text: str, slack_thread_url: str = "") -> dict[str, Any]:
    """Classify whether a Slack message should route directly to ROI JSM instead of PCO."""

    scope = {
        "slack_thread_url": (slack_thread_url or "").strip(),
        "message_text_chars": len(message_text or ""),
    }
    return _verified(
        _detect_roi_ticket_request(message_text),
        scope,
        "Casual NYSS/BD Ops mentions without create/add/log/handle/task wording do not create ROI tickets.",
        "PSM Ops ROI router",
    )


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
def validate_roi_jira_configuration() -> dict[str, Any]:
    """Validate configured ROI JSM project, request type, and required request fields."""

    scope = {"project_key": _env("PSM_OPS_ROI_JIRA_PROJECT_KEY"), "subsystem": "jira_roi"}
    missing = [
        env_name
        for env_name in [
            "JIRA_BASE_URL",
            "JIRA_EMAIL",
            "JIRA_API_TOKEN",
            "SLACK_BOT_TOKEN",
            "PSM_OPS_ROI_JIRA_PROJECT_KEY",
            "PSM_OPS_ROI_JIRA_SERVICE_DESK_ID",
            "PSM_OPS_ROI_JIRA_REQUEST_TYPE_ID",
        ]
        if not _env(env_name)
    ]
    if missing:
        return _blocked(f"Missing ROI Jira config: {', '.join(missing)}", scope, "Jira ROI")

    try:
        fields = _roi_request_type_fields()
        if not fields:
            return _blocked("ROI request type metadata returned no fields.", scope, "Jira ROI")
        mapping, ambiguous = _roi_field_mapping(fields)
    except JiraError as error:
        return _blocked(str(error), scope, "Jira ROI")

    if ambiguous:
        return _blocked(f"Ambiguous ROI request field mapping: {', '.join(ambiguous)}", scope, "Jira ROI")

    required_fields = [_roi_field_name(field) for field in fields if _roi_field_required(field)]
    unsupported_required = [
        _roi_field_name(field)
        for field in fields
        if _roi_field_required(field) and not _roi_field_key(field)
    ]
    if unsupported_required:
        return _blocked(
            "ROI required fields need explicit config: " + ", ".join(sorted(set(unsupported_required))),
            {**scope, "required_fields": required_fields},
            "Jira ROI",
        )

    return _verified(
        {
            "project_key": _roi_project_key(),
            "service_desk_id": _roi_service_desk_id(),
            "request_type_id": _roi_request_type_id(),
            "required_fields": required_fields,
            "mapped_fields": sorted(mapping.keys()),
            "configured_field_ids": _configured_roi_field_ids(),
            "requester_rule": "explicit requested/reported-by wins; otherwise current Slack sender; unresolved requester blocks creation",
        },
        scope,
        "ROI request type metadata is reachable and required fields are mapped.",
        "Jira ROI",
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
        caller = _caller(slack_user_email, require_jira_account=False, require_ps_team=True)
        ps_team = caller["ps_team"]
        clauses = [
            f"project = {_project_key()}",
            f"{_jql_field_ref(_ps_team_field_id())} = {_quote_jql(ps_team)}",
        ]
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

    return _verified(
        [_safe_issue(issue) for issue in issues],
        {
            **scope,
            "caller": caller["slack_email"],
            "ps_team": caller["ps_team"],
            "ps_team_option_id": caller.get("ps_team_option_id", ""),
            "jira_account_id": caller.get("jira_account_id", ""),
        },
    )


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
    ps_team: str = "",
    request_type_key: str = "customer_next_action",
) -> dict[str, Any]:
    """Build a Jira-ready PCO task draft without creating it."""

    scope = {"caller": (slack_user_email or "").strip().lower(), "customer": customer, "request_type_key": request_type_key}
    normalized_ps_team = _normalize_ps_team(ps_team) or _infer_ps_team_from_text(summary, action_type, risk_reason, customer)
    try:
        caller = _caller(slack_user_email, require_jira_account=not _is_thin_poc(), require_ps_team=not bool(normalized_ps_team))
        request_type_id = _request_type_id(request_type_key)
        _configured_fields()
    except JiraError as error:
        return _blocked(str(error), scope)

    if not customer or not summary:
        return _blocked("Customer and summary are required for a PCO task draft.", scope)

    normalized_ps_team = normalized_ps_team or str(caller.get("ps_team") or "").strip()
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
        "owner_jira_account_id": caller.get("jira_account_id", ""),
        "contributor_cse": contributor_cse.strip(),
        "ps_team": normalized_ps_team,
        "request_type_key": request_type_key,
        "request_type_id": request_type_id,
        "approval_required": True,
        "mode": _jira_mode(),
    }
    duplicates = _duplicate_candidates(draft["customer"], draft["summary"])
    return _verified(
        {"draft": draft, "duplicate_candidates": duplicates},
        {
            **scope,
            "caller": caller["slack_email"],
            "ps_team": normalized_ps_team,
            "jira_account_id": caller.get("jira_account_id", ""),
        },
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
        _validate_due_date_for_write(str(draft.get("due_date") or ""))
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
def find_roi_ticket_by_slack_thread(slack_thread_url: str, max_results: int = 5) -> dict[str, Any]:
    """Find existing ROI tickets that already cite a Slack thread permalink."""

    source = (slack_thread_url or "").strip()
    scope = {"slack_thread_url": source, "max_results": max(1, min(int(max_results or 5), 20)), "subsystem": "jira_roi"}
    if not source:
        return _blocked("Slack thread URL is required for ROI ticket traceability.", scope, "Jira ROI")
    try:
        matches = _roi_ticket_by_slack_thread(source, scope["max_results"])
    except JiraError as error:
        return _blocked(str(error), scope, "Jira ROI")
    return _verified(
        {"matches": matches},
        scope,
        "Same Slack thread permalink is the ROI ticket idempotency key.",
        "Jira ROI",
    )


@mcp.tool()
def create_roi_ticket_from_slack(
    slack_user_email: str,
    slack_thread_url: str,
    message_text: str = "",
    customer: str = "",
    staffany_orgs: list[str] | None = None,
    summary: str = "",
    details: str = "",
    request_category: str = "",
    original_channel: str = "",
    requester: str = "",
    evidence_links: list[str] | None = None,
    priority: str = "",
) -> dict[str, Any]:
    """Create a direct ROI JSM ticket from an actionable PS WEE Slack request."""

    source = (slack_thread_url or "").strip()
    links = [str(link).strip() for link in (evidence_links or []) if str(link).strip()]
    normalized_customer = (customer or "").strip()
    normalized_staffany_orgs = [str(org).strip() for org in (staffany_orgs or []) if str(org).strip()]
    if not normalized_staffany_orgs and normalized_customer:
        normalized_staffany_orgs = [normalized_customer]
    intent_text = "\n".join(
        part
        for part in [
            message_text,
            summary,
            details,
            request_category,
            normalized_customer,
        ]
        if part
    )
    scope = {
        "caller": (slack_user_email or "").strip().lower(),
        "slack_thread_url": source,
        "customer": normalized_customer,
        "subsystem": "jira_roi",
    }
    if not source:
        return _blocked("Slack thread URL is required before creating a traceable ROI ticket.", scope, "Jira ROI")

    intent = _detect_roi_ticket_request(intent_text)
    if not intent["is_roi_ticket_request"]:
        return _blocked(
            "This is not an actionable ROI/RevOps/BD Ops ticket request. Ask PS Wee to create, add, log, handle, or ticket the work.",
            {**scope, "intent": intent},
            "Jira ROI",
        )

    try:
        existing = _roi_ticket_by_slack_thread(source, 5)
        if existing:
            answer = {"existing_ticket": existing[0], "duplicate_candidates": existing}
            answer["central_copy"] = post_ps_wee_audit(
                "roi_ticket_reused",
                source_thread_url=source,
                issue_key=str(existing[0].get("issue_key") or ""),
                issue_url=str(existing[0].get("url") or ""),
                requester=scope["caller"],
                customer=normalized_customer,
                summary=str(existing[0].get("summary") or summary or "ROI request from Slack"),
                status=str(existing[0].get("status") or ""),
                jira_payload=answer,
                extra={"subsystem": "jira_roi"},
            )
            return _verified(
                answer,
                scope,
                "Existing ROI ticket found for the same Slack thread; update it instead of creating a duplicate.",
                "Jira ROI",
            )

        requester_identity, requester_source, requester_query = _resolve_roi_requester(slack_user_email, requester, message_text)
        fields = _roi_request_type_fields()
        if not fields:
            return _blocked("ROI request type metadata returned no fields.", scope, "Jira ROI")

        roi_summary = _compact_roi_summary(summary, message_text, normalized_customer)
        roi_category = (request_category or "").strip() or _infer_roi_category(message_text, summary, details)
        requester_text = _roi_requester_text(requester_identity)
        description = _roi_metadata_comment(
            {
                "slack_thread_url": source,
                "original_channel": (original_channel or "").strip(),
                "requester_text": requester_text,
                "requester_source": requester_source,
                "customer": normalized_customer,
                "staffany_orgs": normalized_staffany_orgs,
                "request_category": roi_category,
                "priority": (priority or "").strip(),
                "summary": roi_summary,
                "details": (details or message_text or "").strip(),
                "evidence_links": links,
            }
        )
        draft = {
            "slack_thread_url": source,
            "original_channel": (original_channel or "").strip(),
            "requester_text": requester_text,
            "requester_slack": requester_query,
            "requester_source": requester_source,
            "requester_jira_account_id": requester_identity["jira_account_id"],
            "customer": normalized_customer,
            "staffany_orgs": normalized_staffany_orgs,
            "request_category": roi_category,
            "priority": (priority or "").strip(),
            "summary": roi_summary,
            "details": (details or message_text or "").strip(),
            "description": description,
            "evidence_links": links,
            "intent": intent,
        }
        request_values, missing_required = _roi_request_field_values(fields, draft)
        if missing_required:
            return _blocked(
                "Missing required ROI fields: " + ", ".join(missing_required),
                {**scope, "missing_fields": missing_required, "requester": requester_text},
                "Jira ROI",
            )
        payload = {
            "serviceDeskId": _roi_service_desk_id(),
            "requestTypeId": _roi_request_type_id(),
            "requestFieldValues": request_values,
            "isAdfRequest": False,
            "raiseOnBehalfOf": requester_identity["jira_account_id"],
        }
        response = _request_json("POST", "/rest/servicedeskapi/request", payload)
    except JiraError as error:
        return _blocked(str(error), scope, "Jira ROI")

    warnings: list[str] = []
    issue_key = str(response.get("issueKey") or response.get("issueId") or response.get("key") or "").strip()
    issue_url = _issue_url(issue_key) if issue_key else ""
    if issue_key:
        try:
            _add_internal_jsm_comment(issue_key, description)
        except JiraError:
            warnings.append("ROI ticket was created but Slack metadata internal comment could not be added.")
    ticket_ref = f"<{issue_url}|{issue_key}>" if issue_key and issue_url else issue_key or issue_url or "the ROI ticket"
    answer = {
        "issue_key": issue_key,
        "url": issue_url,
        "jira_response": {key: response.get(key) for key in ["issueId", "issueKey", "requestTypeId"] if key in response},
        "requester": requester_text,
        "requester_source": requester_source,
        "warnings": warnings,
        "slack_reply": f"Created ROI ticket: {ticket_ref}. Requester: {requester_text}.",
    }
    answer["central_copy"] = post_ps_wee_audit(
        "roi_ticket_created",
        source_thread_url=source,
        issue_key=issue_key,
        issue_url=issue_url,
        requester=requester_text,
        customer=normalized_customer,
        summary=roi_summary,
        status="created",
        jira_payload={"draft": draft, "request_payload": payload, "answer": answer},
        extra={"subsystem": "jira_roi"},
    )
    return _verified(answer, scope, "ROI ticket is source of truth; Slack thread is evidence.", "Jira ROI")


PS_WEE_DEFAULT_MISSING_INFO = [
    "customer/org",
    "issue details",
    "impact/urgency",
    "affected outlet/user/date range",
    "expected outcome",
    "screenshots/logs if relevant",
]

PS_WEE_SLACK_MISSING_INFO_LIMIT = 2


def _has_any_text(*values: Any) -> bool:
    return any(bool(str(value or "").strip()) for value in values)


def _text_contains_any(text: str, needles: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(needle in lowered for needle in needles)


def _ps_wee_missing_info(
    *,
    supplied_missing_info: list[str] | None,
    customer: str,
    customer_channel_mapping: dict[str, Any],
    issue_summary: str,
    known_details: str,
    impact: str,
    affected_scope: str,
    expected_outcome: str,
    evidence_links: list[str] | None,
) -> tuple[list[str], list[str]]:
    candidates = [str(item).strip() for item in (supplied_missing_info or PS_WEE_DEFAULT_MISSING_INFO) if str(item).strip()]
    known_text = " ".join(
        str(value or "")
        for value in [
            customer,
            issue_summary,
            known_details,
            impact,
            affected_scope,
            expected_outcome,
            " ".join(str(link or "") for link in (evidence_links or [])),
        ]
    )
    has_customer = _has_any_text(customer) or bool(customer_channel_mapping)
    has_issue_details = _has_any_text(issue_summary, known_details)
    has_impact = _has_any_text(impact) or _text_contains_any(
        known_text,
        ["blocked", "unable", "cannot", "can't", "not able", "failed", "limit", "error"],
    )
    has_affected_scope = _has_any_text(affected_scope) or _text_contains_any(
        known_text,
        ["affected", "outlet", "staff", "user", "profile", "employee", "date range"],
    )
    has_expected_outcome = _has_any_text(expected_outcome) or _text_contains_any(
        known_text,
        ["workaround", "resolve", "fix", "follow up", "check ", "advise", "expected outcome"],
    )
    has_evidence = bool([link for link in (evidence_links or []) if str(link or "").strip()]) or _text_contains_any(
        known_text,
        ["screenshot", "log", "intercom", "support thread", "slack thread", "attached"],
    )
    known_by_field = {
        "customer/org": has_customer,
        "issue details": has_issue_details,
        "impact/urgency": has_impact,
        "affected outlet/user/date range": has_affected_scope,
        "expected outcome": has_expected_outcome,
        "screenshots/logs if relevant": has_evidence,
    }
    missing = []
    seen = set()
    for item in candidates:
        if item in seen:
            continue
        seen.add(item)
        if known_by_field.get(item) is True:
            continue
        missing.append(item)
    return missing, missing[:PS_WEE_SLACK_MISSING_INFO_LIMIT]


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
    ps_team: str = "",
) -> dict[str, Any]:
    """Create an immediate PCO intake ticket for PS WEE/PSM Manager Ops requests."""

    source = (slack_thread_url or "").strip()
    supplied_customer = (customer or "").strip()
    normalized_customer = supplied_customer or "Unknown customer"
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
            answer = {"existing_ticket": existing[0], "duplicate_candidates": existing}
            answer["central_copy"] = post_ps_wee_audit(
                "ticket_reused",
                source_thread_url=source,
                issue_key=str(existing[0].get("issue_key") or ""),
                issue_url=str(existing[0].get("url") or ""),
                requester=scope["caller"],
                customer=normalized_customer,
                summary=str(existing[0].get("summary") or normalized_issue),
                status=str(existing[0].get("status") or ""),
                jira_payload=answer,
                extra={"request_type_key": request_type_key},
            )
            return _verified(
                answer,
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
        customer_channel_mapping: dict[str, Any] = {}
        try:
            customer_channel_mapping = _reviewed_customer_channel_mapping(source, supplied_customer)
        except CustomerChannelMapMiss:
            customer_channel_mapping = {}
        if customer_channel_mapping:
            normalized_customer = customer_channel_mapping["customer_name"]
            scope["customer"] = normalized_customer
            scope["channel_id"] = customer_channel_mapping["channel_id"]
            scope["customer_channel_mapping"] = "reviewed"
        request_type_id = _request_type_id(request_type_key)
        _configured_fields()
    except JiraError as error:
        return _blocked(str(error), scope)

    full_missing, slack_missing = _ps_wee_missing_info(
        supplied_missing_info=missing_info,
        customer=normalized_customer if supplied_customer or customer_channel_mapping else "",
        customer_channel_mapping=customer_channel_mapping,
        issue_summary=normalized_issue if issue_summary else "",
        known_details=known_details,
        impact=impact,
        affected_scope=affected_scope,
        expected_outcome=expected_outcome,
        evidence_links=evidence_links,
    )
    source_links = [source]
    source_links.extend(str(link).strip() for link in (evidence_links or []) if str(link).strip())
    normalized_ps_team = _normalize_ps_team(ps_team) or _infer_ps_team_from_text(
        normalized_issue,
        known_details,
        affected_scope,
        expected_outcome,
        normalized_customer,
    )
    draft = {
        "customer": normalized_customer,
        "summary": f"[Needs info] {normalized_customer} - {normalized_issue}",
        "due_date": due_date.strip(),
        "action_type": "PS WEE ticket intake",
        "priority": (priority or "Medium").strip(),
        "risk_reason": "Needs info from Slack thread",
        "source_links": source_links,
        "staffany_orgs": customer_channel_mapping.get("staffany_orgs", []),
        "ps_team": normalized_ps_team,
        "owner_psm": caller["display_name"],
        "owner_jira_account_id": caller.get("jira_account_id", ""),
        "contributor_cse": "",
        "request_type_key": request_type_key,
        "request_type_id": request_type_id,
        "approval_required": False,
        "mode": _jira_mode(),
        "slack_thread_url": source,
        "known_details": (known_details or "").strip(),
        "missing_info": full_missing,
        "impact": (impact or "").strip(),
        "affected_scope": (affected_scope or "").strip(),
        "expected_outcome": (expected_outcome or "").strip(),
        "customer_channel_id": customer_channel_mapping.get("channel_id", ""),
        "customer_channel_name": customer_channel_mapping.get("channel_name", ""),
        "customer_channel_customer_key": customer_channel_mapping.get("customer_key", ""),
        "add_needs_info_label": True,
    }
    result = _create_pco_task_from_draft(draft, scope)
    if result.get("confidence") != "verified":
        return result
    answer = result.get("answer", {})
    answer["missing_info"] = slack_missing
    issue_key = str(answer.get("issue_key") or "").strip()
    issue_url = str(answer.get("url") or "").strip()
    ticket_ref = f"<{issue_url}|{issue_key}>" if issue_key and issue_url else issue_key or issue_url or "the ticket"
    if slack_missing:
        answer["slack_reply"] = (
            f"Created first so this won't be missed: {ticket_ref}. "
            f"I still need: {', '.join(slack_missing)}."
        )
    else:
        answer["slack_reply"] = f"Created first so this won't be missed: {ticket_ref}. No extra info needed from Slack right now."
    answer["central_copy"] = post_ps_wee_audit(
        "ticket_created",
        source_thread_url=source,
        issue_key=issue_key,
        issue_url=issue_url,
        requester=scope["caller"],
        customer=normalized_customer,
        summary=normalized_issue,
        status="created",
        missing_info=full_missing,
        jira_payload={"draft": draft, "answer": answer},
        extra={"request_type_key": request_type_key},
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
        ("ROI issue", draft.get("roi_issue_key")),
        ("ROI URL", draft.get("roi_issue_url")),
        ("Original channel", draft.get("original_channel")),
        ("Tracker type", draft.get("tracker_type")),
        ("Missing info", ", ".join(draft.get("missing_info") or [])),
        ("Source links", ", ".join(draft.get("source_links") or [])),
        ("Customer channel", draft.get("customer_channel_id")),
        ("Customer channel name", draft.get("customer_channel_name")),
        ("Customer 360 customer key", draft.get("customer_channel_customer_key")),
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


@mcp.tool()
def set_pco_assignee(
    issue_key: str,
    assignee: str,
    slack_user_email: str = "",
    comment: str = "",
) -> dict[str, Any]:
    """Assign a PCO issue to an active Jira user resolved from Slack mention, email, or exact name."""

    key = (issue_key or "").strip().upper()
    target = (assignee or "").strip()
    scope = {"issue_key": key, "assignee": target, "caller": (slack_user_email or "").strip().lower()}
    if not key:
        return _blocked("Issue key is required.", scope)
    if not target:
        return _blocked("Assignee is required.", scope)
    try:
        jira_user = _jira_assignable_user_for_issue(key, target)
        _assign_issue(key, jira_user["jira_account_id"])
        if comment:
            add_internal_pco_comment(key, f"Assignee updated to {jira_user['display_name']}. Context: {comment}", slack_user_email)
    except JiraError as error:
        return _blocked(str(error), scope)
    return _verified(
        {
            "issue_key": key,
            "assignee": jira_user["display_name"],
            "jira_account_id": jira_user["jira_account_id"],
        },
        {**scope, "assignee": jira_user["display_name"]},
        "Jira assignee was updated. My-task ownership and reminders still use Jira PS Team.",
    )


@mcp.tool()
def set_pco_ps_team(
    issue_key: str,
    ps_team: str,
    slack_user_email: str = "",
    comment: str = "",
) -> dict[str, Any]:
    """Set the PCO PS Team field, e.g. map 'cs duty' to the Jira option 'CS Duty'."""

    key = (issue_key or "").strip().upper()
    normalized = _normalize_ps_team(ps_team) or _infer_ps_team_from_text(ps_team, comment)
    scope = {"issue_key": key, "ps_team": normalized, "caller": (slack_user_email or "").strip().lower()}
    if not key:
        return _blocked("Issue key is required.", scope)
    if not normalized:
        return _blocked("PS Team is required.", scope)
    try:
        issue_value = _ps_team_issue_value(normalized)
        _request_json(
            "PUT",
            f"/rest/api/3/issue/{urllib.parse.quote(key)}",
            {"fields": {_ps_team_field_id(): issue_value}},
        )
        if comment:
            add_internal_pco_comment(key, f"PS Team updated to {normalized}. Context: {comment}")
    except JiraError as error:
        return _blocked(str(error), scope)
    return _verified(
        {"issue_key": key, "ps_team": normalized},
        scope,
        "PS Team was updated on the Jira issue.",
    )


def _normalize_roi_issue_key(value: str) -> str:
    key = _normalize_issue_key(value)
    project_key = _roi_project_key()
    if not re.fullmatch(rf"{re.escape(project_key)}-\d+", key):
        raise JiraError(f"roi_issue_key must look like {project_key}-123.")
    return key


def _link_roi_to_pco_tracker(roi_issue_key: str, pco_issue_key: str) -> dict[str, Any]:
    roi_key = _normalize_roi_issue_key(roi_issue_key)
    pco_key = _normalize_issue_key(pco_issue_key)
    if not PCO_ISSUE_RE.fullmatch(pco_key):
        raise JiraError("pco_issue_key must look like PCO-123.")
    relationship = f"{pco_key} is blocked by {roi_key}"
    if _issue_link_exists_between(pco_key, roi_key, "Blocks"):
        return {
            "pco_issue_key": pco_key,
            "roi_issue_key": roi_key,
            "link_type": "Blocks",
            "relationship": relationship,
            "already_exists": True,
        }
    try:
        _request_json(
            "POST",
            "/rest/api/3/issueLink",
            {
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": roi_key},
                "inwardIssue": {"key": pco_key},
            },
        )
    except JiraError as error:
        if not _looks_like_existing_issue_link_error(error):
            raise
        return {
            "pco_issue_key": pco_key,
            "roi_issue_key": roi_key,
            "link_type": "Blocks",
            "relationship": relationship,
            "already_exists": True,
        }
    return {
        "pco_issue_key": pco_key,
        "roi_issue_key": roi_key,
        "link_type": "Blocks",
        "relationship": relationship,
        "already_exists": False,
    }


@mcp.tool()
def create_or_link_pco_roi_tracker(
    slack_user_email: str,
    slack_thread_url: str,
    roi_issue_key: str,
    customer: str = "",
    staffany_orgs: list[str] | None = None,
    summary: str = "",
    requester: str = "",
    original_channel: str = "",
    evidence_links: list[str] | None = None,
    ps_team: str = "",
) -> dict[str, Any]:
    """Create or reuse one PCO customer-loop tracker for a linked ROI ticket."""

    source = (slack_thread_url or "").strip()
    normalized_customer = (customer or "").strip() or "Unknown customer"
    links = [str(link).strip() for link in (evidence_links or []) if str(link).strip()]
    scope = {
        "caller": (slack_user_email or "").strip().lower(),
        "slack_thread_url": source,
        "roi_issue_key": (roi_issue_key or "").strip().upper(),
        "customer": normalized_customer,
        "subsystem": "jira_pco_roi_tracker",
    }
    if not source:
        return _blocked("Slack thread URL is required before creating a traceable PCO ROI tracker.", scope)

    try:
        roi_key = _normalize_roi_issue_key(roi_issue_key)
        caller = _caller(slack_user_email, require_jira_account=False, require_ps_team=True)
        normalized_ps_team = _normalize_ps_team(ps_team) or str(caller.get("ps_team") or "").strip()
        if not normalized_ps_team:
            raise JiraError("Caller must resolve to Jira PS Team before creating a PCO ROI tracker.")
        existing = _pco_roi_tracker_by_slack_thread(source, 5)
        warnings: list[str] = []
        if existing:
            pco_key = str(existing[0].get("issue_key") or "").strip().upper()
            pco_url = str(existing[0].get("url") or _issue_url(pco_key))
            already_exists = True
        else:
            request_type_id = _request_type_id("customer_next_action")
            source_links = [source, _issue_url(roi_key), *links]
            normalized_staffany_orgs = [
                str(org).strip()
                for org in (staffany_orgs or ([normalized_customer] if normalized_customer != "Unknown customer" else []))
                if str(org).strip()
            ]
            tracker_summary = (summary or "").strip() or f"Customer follow-up waiting on {roi_key}"
            draft = {
                "customer": normalized_customer,
                "summary": f"[Waiting internal] {normalized_customer} - {tracker_summary}",
                "due_date": "",
                "action_type": "ROI customer-loop tracker",
                "priority": "Medium",
                "risk_reason": f"Waiting Internal team via {roi_key}",
                "source_links": source_links,
                "staffany_orgs": normalized_staffany_orgs,
                "ps_team": normalized_ps_team,
                "owner_psm": caller.get("display_name") or caller.get("slack_email") or scope["caller"],
                "owner_jira_account_id": caller.get("jira_account_id", ""),
                "contributor_cse": "",
                "request_type_key": "customer_next_action",
                "request_type_id": request_type_id,
                "approval_required": False,
                "mode": _jira_mode(),
                "slack_thread_url": source,
                "known_details": (summary or "").strip(),
                "missing_info": [],
                "impact": "",
                "affected_scope": "",
                "expected_outcome": "Close the customer loop after ROI resolves the internal billing work.",
                "roi_issue_key": roi_key,
                "roi_issue_url": _issue_url(roi_key),
                "original_channel": (original_channel or "").strip(),
                "tracker_type": "PCO customer-loop tracker for ROI",
                "customer_channel_id": "",
                "customer_channel_name": "",
                "customer_channel_customer_key": "",
            }
            result = _create_pco_task_from_draft(draft, scope)
            if result.get("confidence") != "verified":
                return result
            answer = result.get("answer", {})
            pco_key = str(answer.get("issue_key") or "").strip().upper()
            pco_url = str(answer.get("url") or _issue_url(pco_key))
            warnings.extend(answer.get("warnings") or [])
            already_exists = False
            try:
                _update_issue_labels(pco_key, add=[ROI_TRACKER_LABEL])
            except JiraError:
                warnings.append(f"PCO tracker was created but the {ROI_TRACKER_LABEL} label could not be set.")

        link = _link_roi_to_pco_tracker(roi_key, pco_key)
        status = str((existing[0].get("status") if existing else "") or "").strip()
        if status.lower() != "waiting internal":
            transition = transition_pco_task(
                pco_key,
                "Waiting Internal",
                slack_user_email,
                f"PCO customer-loop tracker is waiting on linked ROI issue {roi_key}.",
            )
            if transition.get("confidence") != "verified":
                warnings.append(f"PCO tracker exists but could not be moved to Waiting Internal: {transition.get('caveat')}")
        ticket_ref = f"<{pco_url}|{pco_key}>" if pco_key and pco_url else pco_key
        roi_ref = f"<{_issue_url(roi_key)}|{roi_key}>"
        answer = {
            "pco_issue_key": pco_key,
            "pco_url": pco_url,
            "roi_issue_key": roi_key,
            "roi_url": _issue_url(roi_key),
            "relationship": link["relationship"],
            "already_exists": already_exists,
            "link_already_exists": link["already_exists"],
            "label": ROI_TRACKER_LABEL,
            "ps_team": normalized_ps_team,
            "warnings": warnings,
            "slack_reply": f"Tracking customer loop on PCO: {ticket_ref} linked to {roi_ref} and set to Waiting Internal.",
        }
        answer["central_copy"] = post_ps_wee_audit(
            "roi_tracker_linked",
            source_thread_url=source,
            issue_key=pco_key,
            issue_url=pco_url,
            requester=requester or caller.get("display_name") or scope["caller"],
            customer=normalized_customer,
            summary=summary or f"Customer loop waiting on {roi_key}",
            status="Waiting Internal",
            jira_payload=answer,
            extra={"subsystem": "jira_pco_roi_tracker", "roi_issue_key": roi_key},
        )
    except JiraError as error:
        return _blocked(str(error), scope)

    return _verified(
        answer,
        {**scope, "roi_issue_key": roi_key, "pco_issue_key": pco_key},
        "ROI remains source of truth; PCO tracker is only the customer-loop visibility task.",
    )


@mcp.tool()
def link_pco_to_engineering_issue(
    pco_issue_key: str,
    engineering_issue_key: str,
    link_type: str = "Blocks",
) -> dict[str, Any]:
    """Link a PCO issue to a KER/SCHE issue with a narrow allowlist."""

    pco_key = _normalize_issue_key(pco_issue_key)
    engineering_key = _normalize_issue_key(engineering_issue_key)
    normalized_link_type = _normalize_issue_link_type(link_type)
    scope = {
        "pco_issue_key": pco_key,
        "engineering_issue_key": engineering_key,
        "link_type": normalized_link_type or (link_type or "").strip(),
    }
    if not PCO_ISSUE_RE.fullmatch(pco_key):
        return _blocked("pco_issue_key must look like PCO-123.", scope)
    if not ENGINEERING_LINK_TARGET_RE.fullmatch(engineering_key):
        return _blocked("engineering_issue_key must look like KER-123 or SCHE-123.", scope)
    if normalized_link_type not in {"Blocks", "Relates"}:
        return _blocked("link_type must be Blocks or Relates.", scope)

    if normalized_link_type == "Blocks":
        body = {
            "type": {"name": "Blocks"},
            "outwardIssue": {"key": engineering_key},
            "inwardIssue": {"key": pco_key},
        }
        relationship = f"{pco_key} is blocked by {engineering_key}"
    else:
        body = {
            "type": {"name": "Relates"},
            "outwardIssue": {"key": pco_key},
            "inwardIssue": {"key": engineering_key},
        }
        relationship = f"{pco_key} relates to {engineering_key}"

    try:
        if _issue_link_exists(pco_key, engineering_key, normalized_link_type):
            return _verified(
                {
                    "pco_issue_key": pco_key,
                    "engineering_issue_key": engineering_key,
                    "link_type": normalized_link_type,
                    "relationship": relationship,
                    "already_exists": True,
                },
                scope,
                "Issue link already existed; checked issue links only, without reading Jira comments or descriptions.",
            )
        _request_json("POST", "/rest/api/3/issueLink", body)
    except JiraError as error:
        if _looks_like_existing_issue_link_error(error):
            return _verified(
                {
                    "pco_issue_key": pco_key,
                    "engineering_issue_key": engineering_key,
                    "link_type": normalized_link_type,
                    "relationship": relationship,
                    "already_exists": True,
                },
                scope,
                "Jira reported the issue link already exists; no raw Jira comments or descriptions were exposed.",
            )
        return _blocked(str(error), scope)

    return _verified(
        {
            "pco_issue_key": pco_key,
            "engineering_issue_key": engineering_key,
            "link_type": normalized_link_type,
            "relationship": relationship,
            "already_exists": False,
        },
        scope,
        "Issue link created only between PCO and KER/SCHE; no raw Jira issue content was read or exposed.",
    )


def _set_issue_due_date(issue_key: str, due_date: str) -> None:
    value = _validate_due_date_for_write(due_date)
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
    slack_poster_name: str = "",
    slack_poster_user_id: str = "",
    slack_poster_email: str = "",
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
    poster_name = slack_poster_name.strip()
    poster_user_id = slack_poster_user_id.strip()
    if poster_user_id.startswith("<@") and poster_user_id.endswith(">"):
        poster_user_id = poster_user_id[2:-1]
    poster_email = slack_poster_email.strip().lower()
    if slack_user_email.strip() and (not poster_name or not poster_user_id or not poster_email):
        slack_user = _resolve_slack_user(slack_user_email)
        if slack_user:
            profile = slack_user.get("profile") or {}
            poster_name = poster_name or (
                str(profile.get("real_name") or "").strip()
                or str(slack_user.get("real_name") or "").strip()
                or str(profile.get("display_name") or "").strip()
            )
            poster_user_id = poster_user_id or str(slack_user.get("id") or "").strip()
            poster_email = poster_email or _slack_user_email(slack_user)
        poster_email = poster_email or _normalize_slack_email(slack_user_email)
    poster_parts = []
    if poster_name:
        poster_parts.append(poster_name)
    if poster_user_id:
        poster_parts.append(f"<@{poster_user_id}>")
    if poster_email:
        poster_parts.append(poster_email)
    if poster_parts:
        lines.append(f"Slack poster: {' '.join(poster_parts)}")
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
    result = add_internal_pco_comment(key, "\n".join(lines), slack_user_email)
    if result.get("confidence") == "verified":
        answer = result.get("answer", {})
        answer["central_copy"] = post_ps_wee_audit(
            "ticket_update_synced",
            source_thread_url=source,
            issue_key=key,
            issue_url=_issue_url(key),
            requester=scope["caller"],
            summary=summary,
            status="update synced",
            jira_payload={
                "issue_key": key,
                "update_summary": summary,
                "updated_fields": fields,
                "evidence_links": links,
                "comment": answer,
            },
        )
    return result


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
    answer["central_copy"] = post_ps_wee_audit(
        "ticket_ready",
        source_thread_url=source,
        issue_key=key,
        issue_url=_issue_url(key),
        requester=scope["caller"],
        summary=(ready_summary or "").strip(),
        status="ready for triage",
        jira_payload={"issue_key": key, "ready_summary": ready_summary, "warnings": warnings, "comment": comment_result.get("answer", {})},
    )
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
            "reminder_policy": "Jira due date is the reminder source. Central PSM Ops digests run at 09:00 SGT and 17:00 SGT while the issue is not Done.",
            "central_digest": "No separate Slack thread or local reminder was created.",
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
            caller = _caller(slack_user_email, require_jira_account=False, require_ps_team=True)
            clauses.append(f"{_jql_field_ref(_ps_team_field_id())} = {_quote_jql(caller['ps_team'])}")
            scope["caller"] = caller["slack_email"]
            scope["ps_team"] = caller["ps_team"]
            scope["ps_team_option_id"] = caller.get("ps_team_option_id", "")
            scope["jira_account_id"] = caller.get("jira_account_id", "")
        jql = " AND ".join(clauses) + " ORDER BY duedate ASC, updated DESC"
        issues = _search_issues(jql, _search_fields(), max_results)
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
