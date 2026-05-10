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
from datetime import date, datetime, time as datetime_time, timedelta, timezone
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
    "lifecyclestage",
    "type",
    "contract_end_date",
    "current_tool_renewal_date",
    "current_tools",
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
    "createdate",
    "closedate",
    "hs_lastmodifieddate",
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

MARKETING_CONTACT_PROPERTIES = [
    "email",
    "firstname",
    "lastname",
    "jobtitle",
    "hubspot_owner_id",
    "createdate",
    "lastmodifieddate",
    "lifecyclestage",
    "hs_analytics_source",
    "hs_analytics_source_data_1",
    "hs_analytics_source_data_2",
    "hs_latest_source",
    "hs_latest_source_data_1",
    "hs_latest_source_data_2",
    "first_conversion_event_name",
    "first_conversion_date",
    "recent_conversion_event_name",
    "recent_conversion_date",
    "abm_campaign_tag",
    "ad_interaction",
    "utm_campaign",
]

MARKETING_COMPANY_PROPERTIES = sorted(
    set(
        COMPANY_PROPERTIES
        + [
            "campaign",
            "abm_campaign_tag",
            "ad_interaction",
            "utm_campaign",
            "hs_analytics_source",
            "hs_analytics_source_data_1",
            "hs_analytics_source_data_2",
            "hs_latest_source",
            "hs_latest_source_data_1",
            "hs_latest_source_data_2",
        ]
    )
)

CAMPAIGN_PROPERTIES = [
    "hs_name",
    "hs_campaign_status",
    "hs_start_date",
    "hs_end_date",
    "hs_notes",
    "hs_audience",
    "hs_utm",
    "hs_owner",
    "hs_object_id",
    "hs_budget_items_sum_amount",
    "hs_spend_items_sum_amount",
]

MARKETING_CAMPAIGN_ASSET_TYPES = (
    "FORM",
    "LANDING_PAGE",
    "SITE_PAGE",
    "MARKETING_EMAIL",
    "MARKETING_SMS",
    "SOCIAL_BROADCAST",
    "PODCAST_EPISODE",
)

NO_METRIC_CAMPAIGN_ASSET_TYPES = {"PODCAST_EPISODE", "AD_CAMPAIGN", "MEDIA", "PLAYBOOK", "SALES_DOCUMENT", "EMAIL", "SEQUENCE"}

COMMUNICATION_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_communication_channel_type",
    "hs_communication_logged_from",
    "hs_lastmodifieddate",
]
COMMUNICATION_EVENT_PROPERTIES = [*COMMUNICATION_PROPERTIES, "hs_communication_body"]

NOTE_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_lastmodifieddate",
]

CALL_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_call_title",
    "hs_call_status",
    "hs_call_duration",
    "hs_lastmodifieddate",
]

MEETING_PROPERTIES = [
    "hs_timestamp",
    "hubspot_owner_id",
    "hs_meeting_title",
    "hs_meeting_outcome",
    "hs_activity_type",
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
PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT = 5
HUBSPOT_SEARCH_PAGE_LIMIT = 100
HUBSPOT_SEARCH_RESULT_LIMIT = 1000
HUBSPOT_SEARCH_TOTAL_LIMIT = 10_000
TASK_ASSOCIATION_LIMIT = 100
TASK_RETURN_LIMIT = 100
LUMA_MATCH_DOMAIN_LIMIT = 100
LUMA_MATCH_NAME_LIMIT = 100
LUMA_MATCH_RETURN_LIMIT = 100
TASK_SEARCH_RESULT_LIMIT = 300
TASK_SEARCH_AIRTIGHT_RESULT_LIMIT = 10_000
FOLLOWUP_ASSOCIATION_LIMIT = 100
FOLLOWUP_RETURN_LIMIT = 100
INBOUND_THREAD_RETURN_LIMIT = 50
INBOUND_MESSAGE_RETURN_LIMIT = 100
MARKETING_CAMPAIGN_RETURN_LIMIT = 100
CAMPAIGN_ASSET_RETURN_LIMIT = 100
MESSAGE_TEXT_LIMIT = 4000
PRIORITY_ACCOUNT_RETURN_LIMIT = 1000
PRIORITY_ACCOUNT_LOCKED_POOL_BASELINE = 150
PRIORITY_ACCOUNT_WEEKLY_WORKED_TARGET = 120
CONNECTED_CALL_WEEKLY_TARGET = 40
CONNECTED_CALL_MIN_DURATION_MS = 120_000
STALE_ACCOUNT_DAYS = 18
FRIDAY_REVIEW_DETAIL_LIMIT = 25
QO_PIPELINE_IDS_ENV_VAR = "NURTUREANY_QO_PIPELINE_IDS"
QO_STAGE_IDS_ENV_VAR = "NURTUREANY_QO_STAGE_IDS"
QO_MET_STAGE_IDS_ENV_VAR = "NURTUREANY_QO_MET_STAGE_IDS"
CLOSED_WON_STAGE_IDS_ENV_VAR = "NURTUREANY_CLOSED_WON_STAGE_IDS"
WARM_ACTIVITY_LABELS_ENV_VAR = "NURTUREANY_WARM_ACTIVITY_LABELS"
DEFAULT_WARM_ACTIVITY_LABELS = (
    "HHH",
    "LL",
    "coffee",
    "lunch",
    "dinner",
    "cosy",
    "ABM",
    "event",
    "appreciation afternoon",
    "sports",
)
ACCESS_POLICY_ENV_VAR = "NURTUREANY_ACCESS_POLICY_PATH"
SCOPE_SOURCE = "hubspot_nurtureany"
RENEWAL_SOURCE_OF_TRUTH_PROPERTY = "contract_end_date"
CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY = "current_tools"
RENEWAL_DATE_PROPERTIES = (RENEWAL_SOURCE_OF_TRUTH_PROPERTY,)
C360_COMPANY_URL_TEMPLATE_ENV = "NURTUREANY_C360_COMPANY_URL_TEMPLATE"
C360_ORG_URL_TEMPLATE_ENV = "NURTUREANY_C360_ORG_URL_TEMPLATE"
C360_ROUTE_KEY_BY_COMPANY_ID_ENV = "NURTUREANY_C360_ROUTE_KEY_BY_COMPANY_ID"
DEFAULT_C360_COMPANY_URL_TEMPLATE = "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}"
DEFAULT_C360_ORG_URL_TEMPLATE = (
    "https://customer-360-qv4r5xkisq-as.a.run.app/companies/{customer360_route_key}/orgs/{organisation_id}"
)
DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID = {
    # Customer 360's canonical Fei Siong route is slug-keyed. The numeric
    # HubSpot route is accepted by the app but renders fallback demo orgs.
    "1991281569": "fei-siong-group",
}
DRIVE_ALL_RANDOM_FOLDER_ID = "1qXlFnr5TKFtsYNWk7ZywBBctDaae3RY-"
PHOTO_SCAN_LIMIT = 50
PHOTO_MATCH_LIMIT = 5
PHOTO_LUMA_EVENT_CANDIDATE_LIMIT = 3
PHOTO_SOURCE_TYPES = {"drive", "slack"}
PHOTO_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".gif")
PHOTO_CUSTOM_OBJECT_TYPES = {
    "event": "nurture_event",
    "photo": "nurture_event_photo",
    "appearance": "nurture_person_appearance",
}
SINGAPORE_TIMEZONE = timezone(timedelta(hours=8))
LUMA_BASE_URL = "https://public-api.luma.com"
LUMA_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
LUMA_TIMEOUT_SECONDS = 15
LUMA_PAGE_LIMIT = 50
LUMA_EVENT_LOOKBACK_DAYS = 180
LUMA_EVENT_LOOKAHEAD_DAYS = 1
LUMA_MAX_EVENTS_FOR_FOLLOWUP = 50
LUMA_MAX_GUESTS_PER_EVENT = 250
EVENT_TYPE_ALIASES = {
    "hhh": "HR Happy Hour",
    "hr happy hour": "HR Happy Hour",
    "happy hour": "HR Happy Hour",
    "ll": "Leaders Lounge",
    "leaders lounge": "Leaders Lounge",
    "leader lounge": "Leaders Lounge",
    "appreciation afternoon": "Appreciation Afternoon",
    "appreciation": "Appreciation Afternoon",
    "sports": "Sports",
    "sport": "Sports",
}
LOCATION_ALIASES = {
    "singapore": "Singapore",
    "sg": "Singapore",
    "jakarta": "Jakarta",
    "jkt": "Jakarta",
    "bali": "Bali",
    "kuala lumpur": "Kuala Lumpur",
    "kl": "Kuala Lumpur",
}
LOCATION_COUNTRY_MAP = {
    "Singapore": "Singapore",
    "Jakarta": "Indonesia",
    "Bali": "Indonesia",
    "Kuala Lumpur": "Malaysia",
}
GENERIC_EMAIL_DOMAINS = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "icloud.com",
    "me.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
}
EVENT_FOLLOWUP_PHRASES = (
    "thank you",
    "thanks",
    "thanks for attending",
    "terima kasih",
    "makasih",
    "sudah datang",
    "sudah hadir",
    "telah datang",
    "telah hadir",
    "for coming",
    "for joining",
    "attending",
    "hadir",
    "datang",
    "follow up",
    "follow-up",
)


mcp = FastMCP(
    "hubspot_nurtureany",
    instructions=(
        "Read-only HubSpot target-account tools for NurtureAny. "
        "Mutation tools are intentionally not exposed in V1."
    ),
)


class HubSpotError(RuntimeError):
    pass


class LumaEventError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ScopeError(RuntimeError):
    pass


class AccessPolicyError(RuntimeError):
    pass


def _token() -> str:
    token = os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    if not token:
        raise HubSpotError("Missing HUBSPOT_PRIVATE_APP_TOKEN.")
    return token


def _luma_token() -> str:
    token = os.environ.get("LUMA_API_KEY", "").strip()
    if not token:
        raise LumaEventError("Missing LUMA_API_KEY.")
    return token


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _normalize_countries(countries: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    selected = []
    for country in countries or SUPPORTED_COUNTRIES:
        if country in SUPPORTED_COUNTRIES and country not in selected:
            selected.append(country)
    return tuple(selected)


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _entry_email(entry: Any, *keys: str) -> str:
    if isinstance(entry, str):
        return _normalize_email(entry)
    if isinstance(entry, dict):
        for key in keys:
            value = _normalize_email(str(entry.get(key) or ""))
            if value:
                return value
    return ""


def _access_policy_path() -> str:
    return os.environ.get(ACCESS_POLICY_ENV_VAR, "").strip()


def _load_access_policy_file() -> dict[str, Any]:
    path = _access_policy_path()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as error:
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} is invalid JSON: {error}") from error
    if not isinstance(data, dict):
        raise AccessPolicyError(f"{ACCESS_POLICY_ENV_VAR} must point to a JSON object.")
    return data


def _access_policy() -> dict[str, Any]:
    raw = _load_access_policy_file()
    admins = set(OVERALL_ADMINS)
    managers: dict[str, tuple[str, ...]] = {
        email: _normalize_countries(countries) for email, countries in REGIONAL_MANAGERS.items()
    }
    sales_reps: dict[str, dict[str, Any]] = {}
    disabled: set[str] = set()

    for entry in raw.get("admins", []):
        email = _entry_email(entry, "email", "slack_email")
        if email:
            admins.add(email)

    for entry in raw.get("managers", []):
        email = _entry_email(entry, "email", "slack_email")
        if not email:
            continue
        countries = entry.get("countries") if isinstance(entry, dict) else None
        managers[email] = _normalize_countries(_string_list(countries))

    for entry in raw.get("sales_reps", []):
        if not isinstance(entry, dict) or entry.get("active") is False:
            continue
        slack_email = _normalize_email(str(entry.get("slack_email") or entry.get("email") or ""))
        owner_email = _normalize_email(str(entry.get("hubspot_owner_email") or ""))
        if slack_email and owner_email:
            sales_reps[slack_email] = {
                "hubspot_owner_email": owner_email,
                "countries": _normalize_countries(_string_list(entry.get("countries"))),
            }

    for key in ("disabled", "unclassified"):
        for entry in raw.get(key, []):
            email = _entry_email(entry, "email", "slack_email", "hubspot_owner_email")
            if email:
                disabled.add(email)

    return {
        "source": _access_policy_path() or "built-in-admin-manager-defaults",
        "admins": admins - disabled,
        "managers": {email: countries for email, countries in managers.items() if email not in disabled},
        "sales_reps": {
            email: data
            for email, data in sales_reps.items()
            if email not in disabled and data["hubspot_owner_email"] not in disabled
        },
        "disabled": disabled,
    }


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


def _luma_request_json(path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    url = urllib.parse.urljoin(LUMA_BASE_URL, path)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "x-luma-api-key": _luma_token(),
            "accept": "application/json",
            "user-agent": LUMA_USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=LUMA_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        token = os.environ.get("LUMA_API_KEY", "").strip()
        safe_detail = detail.replace(token, "[REDACTED_LUMA_API_KEY]") if token else detail
        raise LumaEventError(f"Luma API failed: {error.code} {safe_detail[:300]}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LumaEventError(f"Luma API request timed out or failed: {reason}") from error


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


def _list_owners(limit: int = 500) -> list[dict[str, Any]]:
    owners: list[dict[str, Any]] = []
    after = ""
    while len(owners) < _bounded_int(limit, default=500, maximum=1000):
        params = {"archived": "false", "limit": "100"}
        if after:
            params["after"] = after
        data = _get("/crm/v3/owners/", params)
        owners.extend(data.get("results", []))
        after = str(data.get("paging", {}).get("next", {}).get("after") or "")
        if not after:
            break
    return owners[: _bounded_int(limit, default=500, maximum=1000)]


_OWNER_EMAIL_BY_ID_CACHE: dict[str, str] = {}
_OWNER_BY_ID_CACHE: dict[str, dict[str, Any]] = {}


def _owner_email_by_id(owner_id: Any) -> str:
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return ""
    if normalized_owner_id in _OWNER_EMAIL_BY_ID_CACHE:
        return _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id]
    owner = _owner_by_id(normalized_owner_id)
    if owner:
        email = _normalize_email(str(owner.get("email") or ""))
        if email:
            _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id] = email
            return email
    return ""


def _owner_by_id(owner_id: Any) -> dict[str, Any]:
    normalized_owner_id = str(owner_id or "").strip()
    if not normalized_owner_id:
        return {}
    if normalized_owner_id in _OWNER_BY_ID_CACHE:
        return _OWNER_BY_ID_CACHE[normalized_owner_id]
    try:
        owner = _get(f"/crm/v3/owners/{urllib.parse.quote(normalized_owner_id, safe='')}", {"archived": "false"})
    except HubSpotError:
        owner = {}
    if owner and str(owner.get("id") or "").strip() == normalized_owner_id:
        _OWNER_BY_ID_CACHE[normalized_owner_id] = owner
        email = _normalize_email(str(owner.get("email") or ""))
        if email:
            _OWNER_EMAIL_BY_ID_CACHE[normalized_owner_id] = email
        return owner
    try:
        for candidate in _list_owners():
            candidate_id = str(candidate.get("id") or "").strip()
            if candidate_id:
                _OWNER_BY_ID_CACHE[candidate_id] = candidate
                email = _normalize_email(str(candidate.get("email") or ""))
                if email:
                    _OWNER_EMAIL_BY_ID_CACHE[candidate_id] = email
    except HubSpotError:
        return {}
    return _OWNER_BY_ID_CACHE.get(normalized_owner_id, {})


def _owner_name_by_id(owner_id: Any) -> str:
    owner = _owner_by_id(owner_id)
    return _owner_name(owner) if owner else ""


def _caller_scope(slack_user_email: str) -> dict[str, Any]:
    email = _normalize_email(slack_user_email)
    if not email:
        return {"kind": "blocked", "email": "", "countries": (), "owner_id": None}
    try:
        policy = _access_policy()
    except AccessPolicyError as error:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None, "blocked_reason": str(error)}
    if email in policy["disabled"]:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None}
    if email in policy["admins"]:
        return {"kind": "admin", "email": email, "countries": SUPPORTED_COUNTRIES, "owner_id": None}
    if email in policy["managers"]:
        return {"kind": "manager", "email": email, "countries": policy["managers"][email], "owner_id": None}
    rep = policy["sales_reps"].get(email)
    if not rep:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None}
    owner = _owner_by_email(rep["hubspot_owner_email"])
    if not owner:
        return {"kind": "blocked", "email": email, "countries": (), "owner_id": None}
    return {
        "kind": "ae",
        "email": email,
        "countries": rep["countries"],
        "owner_id": str(owner["id"]),
        "hubspot_owner_email": rep["hubspot_owner_email"],
    }


def _safe_countries(countries: list[str] | None, allowed: tuple[str, ...]) -> list[str]:
    requested = countries or list(allowed)
    return [country for country in requested if country in allowed]


def _bounded_int(value: Any, default: int, minimum: int = 1, maximum: int = HUBSPOT_SEARCH_RESULT_LIMIT) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = default
    return max(minimum, min(number, maximum))


def _company_id_from_ref(ref: Any) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d+", text):
        return text
    for pattern in (
        r"/record/0-2/(\d+)",
        r"/companies/(\d+)",
        r"(?:companyId|company_id)=([0-9]+)",
    ):
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return ""


def _normalized_company_ids(refs: list[str] | None) -> list[str]:
    company_ids: list[str] = []
    for ref in refs or []:
        company_id = _company_id_from_ref(ref)
        if company_id and company_id not in company_ids:
            company_ids.append(company_id)
    return company_ids


_COMPANY_NAME_STOP_WORDS = {
    "and",
    "co",
    "company",
    "group",
    "inc",
    "incorporated",
    "llc",
    "limited",
    "llp",
    "ltd",
    "pte",
    "pt",
    "sdn",
    "bhd",
    "the",
}


def _company_name_ref(ref: Any) -> str:
    text = str(ref or "").strip()
    if not text or _company_id_from_ref(text):
        return ""
    parsed = urllib.parse.urlparse(text)
    if parsed.scheme and parsed.netloc:
        return ""
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _normalize_company_match_text(value: Any) -> str:
    text = html.unescape(str(value or "")).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [word for word in text.split() if word not in _COMPANY_NAME_STOP_WORDS]
    return " ".join(words)


def _compact_company_match_text(value: Any) -> str:
    return _normalize_company_match_text(value).replace(" ", "")


def _company_search_token(name: str) -> str:
    words = _normalize_company_match_text(name).split()
    useful = [word for word in words if len(word) >= 3]
    return max(useful, key=len) if useful else ""


def _company_search_terms(name: str) -> list[str]:
    normalized = _normalize_company_match_text(name)
    compact = _compact_company_match_text(name)
    terms: list[str] = []
    for term in [compact, *_company_search_token(name).split(), *normalized.split()]:
        if len(term) >= 3 and term not in terms:
            terms.append(term)
    return terms[:5]


def _company_match_candidate(company: dict[str, Any]) -> dict[str, Any]:
    summary = _summarize_company(company)
    return {
        "company_id": summary["company_id"],
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": summary["name"],
        "domain": summary["domain"],
        "country": summary["country"],
        "owner_id": summary["owner_id"],
        "headcount": summary["headcount"],
        "industry": summary["industry"],
        "current_tools": summary["current_tools"],
        "contract_end_date": summary["contract_end_date"],
    }


def _company_name_match_strength(query: str, company: dict[str, Any]) -> str:
    query_text = _normalize_company_match_text(query)
    candidate_text = _normalize_company_match_text(company.get("properties", {}).get("name") or "")
    if not query_text or not candidate_text:
        return "weak"
    if candidate_text == query_text:
        return "exact"
    query_compact = query_text.replace(" ", "")
    candidate_compact = candidate_text.replace(" ", "")
    if query_compact and query_compact == candidate_compact:
        return "compact_exact"
    query_words = set(query_text.split())
    candidate_words = set(candidate_text.split())
    if query_words and query_words.issubset(candidate_words):
        return "token"
    if query_text in candidate_text or candidate_text in query_text:
        return "contains"
    if query_compact and (query_compact in candidate_compact or candidate_compact in query_compact):
        return "compact_contains"
    return "weak"


def _unique_company_results(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for company in results:
        company_id = str(company.get("id") or "")
        if company_id and company_id not in unique:
            unique[company_id] = company
    return list(unique.values())


def _resolve_scoped_company_name(name: str, scope: dict[str, Any], limit: int = 10) -> dict[str, Any]:
    selected = list(scope.get("countries", ()))
    owner_id = str(scope.get("owner_id") or "") if scope.get("kind") == "ae" else None
    if not selected:
        return {"status": "not_found", "input": name, "candidates": []}

    searches: list[dict[str, Any]] = []
    exact_data = _company_search(
        [
            *_target_filters(selected, owner_id),
            {"propertyName": "name", "operator": "EQ", "value": name},
        ],
        limit=limit,
        maximum=limit,
        sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
    )
    searches.append(exact_data)

    for term in _company_search_terms(name):
        token_data = _company_search(
            [
                *_target_filters(selected, owner_id),
                {"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": term},
            ],
            limit=limit,
            maximum=limit,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        searches.append(token_data)

    companies = _unique_company_results([company for data in searches for company in data.get("results", [])])
    if not companies:
        return {"status": "not_found", "input": name, "candidates": []}

    strong_matches = [
        company
        for company in companies
        if _company_name_match_strength(name, company) in {"exact", "compact_exact"}
    ]
    if len(strong_matches) == 1:
        return {
            "status": "resolved",
            "input": name,
            "company_id": str(strong_matches[0]["id"]),
            "match_type": _company_name_match_strength(name, strong_matches[0]),
        }

    token_matches = [
        company
        for company in companies
        if _company_name_match_strength(name, company) in {"token", "contains", "compact_contains"}
    ]
    if not strong_matches and len(token_matches) == 1:
        return {
            "status": "resolved",
            "input": name,
            "company_id": str(token_matches[0]["id"]),
            "match_type": _company_name_match_strength(name, token_matches[0]),
        }

    candidates = [_company_match_candidate(company) for company in (strong_matches or token_matches or companies)]
    return {
        "status": "ambiguous",
        "input": name,
        "candidates": candidates[:limit],
        "candidate_count": len(candidates),
    }


def _company_in_event_scope(company: dict[str, Any], scope: dict[str, Any], countries: list[str], owner_id: str | None) -> bool:
    if not _has_company_access(company, scope):
        return False
    props = company.get("properties", {})
    if countries and props.get("company_country") not in countries:
        return False
    if owner_id and str(props.get("hubspot_owner_id") or "") != str(owner_id):
        return False
    return True


def _contact_search_by_email(email: str, limit: int = 10) -> list[dict[str, Any]]:
    normalized = _normalize_email(email)
    if not normalized:
        return []
    data = _post(
        "/crm/v3/objects/contacts/search",
        {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": normalized}]}],
            "properties": CONTACT_PROPERTIES,
            "limit": max(1, min(limit, 10)),
        },
    )
    return data.get("results", [])


def _event_match_record(company: dict[str, Any], reason: str, confidence: str) -> dict[str, Any]:
    props = company.get("properties", {})
    return {
        "company": company,
        "company_id": str(company.get("id") or ""),
        "match_reason": reason,
        "match_confidence": confidence,
        "owner_id": str(props.get("hubspot_owner_id") or ""),
    }


def _match_luma_guest_to_company(
    guest: dict[str, Any],
    scope: dict[str, Any],
    countries: list[str],
    owner_id: str | None,
) -> dict[str, Any] | None:
    email = _luma_guest_email(guest)
    if email:
        for contact in _contact_search_by_email(email):
            contact_id = str(contact.get("id") or "")
            for company_id in _association_ids("contacts", contact_id, "companies", 10):
                company = _get_company(company_id)
                if _company_in_event_scope(company, scope, countries, owner_id):
                    return _event_match_record(company, "exact_hubspot_contact_email", "verified")

    domain = _email_domain(email)
    if domain and domain not in GENERIC_EMAIL_DOMAINS:
        data = _company_search(
            [
                *_target_filters(countries, owner_id),
                {"propertyName": "domain", "operator": "EQ", "value": domain},
            ],
            limit=10,
            maximum=10,
            sorts=[{"propertyName": "name", "direction": "ASCENDING"}],
        )
        for company in data.get("results", []):
            if _company_in_event_scope(company, scope, countries, owner_id):
                return _event_match_record(company, "exact_email_domain", "verified")

    for company_name in _luma_guest_company_candidates(guest):
        resolved = _resolve_scoped_company_name(company_name, {**scope, "countries": tuple(countries)}, limit=5)
        if resolved.get("status") != "resolved":
            continue
        company = _get_company(str(resolved.get("company_id") or ""))
        if _company_in_event_scope(company, scope, countries, owner_id):
            return _event_match_record(company, "company_name_candidate", "needs-check")
    return None


def _matched_event_companies(
    guests: list[dict[str, Any]],
    scope: dict[str, Any],
    countries: list[str],
    owner_id: str | None,
) -> dict[str, Any]:
    attended_guests = [guest for guest in guests if _luma_checked_in_at(guest)]
    matches: dict[str, dict[str, Any]] = {}
    verified_match_count = 0
    candidate_match_count = 0
    for guest in attended_guests:
        match = _match_luma_guest_to_company(guest, scope, countries, owner_id)
        if not match:
            continue
        company_id = match["company_id"]
        existing = matches.get(company_id)
        if match["match_confidence"] == "verified":
            verified_match_count += 1
        else:
            candidate_match_count += 1
        if existing:
            existing["attended_match_count"] += 1
            if match["match_reason"] not in existing["match_reasons"]:
                existing["match_reasons"].append(match["match_reason"])
            if existing["match_confidence"] != "verified" and match["match_confidence"] == "verified":
                existing["match_confidence"] = "verified"
                existing["company"] = match["company"]
            continue
        matches[company_id] = {
            "company": match["company"],
            "company_id": company_id,
            "match_confidence": match["match_confidence"],
            "match_reasons": [match["match_reason"]],
            "attended_match_count": 1,
        }
    return {
        "matches": matches,
        "attended_guest_count": len(attended_guests),
        "matched_guest_count": sum(item["attended_match_count"] for item in matches.values()),
        "unmatched_attended_guest_count": max(0, len(attended_guests) - sum(item["attended_match_count"] for item in matches.values())),
        "verified_match_count": verified_match_count,
        "candidate_match_count": candidate_match_count,
    }


def _resolve_pre_demo_company_refs(
    refs: list[str] | None,
    scope: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    selected_refs = list(refs or [])
    selected_refs = selected_refs[:limit]
    resolved_ids: list[str] = []
    resolved_matches: list[dict[str, Any]] = []
    ambiguous_matches: list[dict[str, Any]] = []
    not_found: list[dict[str, Any]] = []

    for ref in selected_refs:
        company_id = _company_id_from_ref(ref)
        if company_id:
            if company_id not in resolved_ids:
                resolved_ids.append(company_id)
            resolved_matches.append({"input": str(ref), "company_id": company_id, "match_type": "id_or_link"})
            continue

        company_name = _company_name_ref(ref)
        if not company_name:
            not_found.append({"input": str(ref), "reason": "not a HubSpot company ID, company link, or usable company name"})
            continue

        match = _resolve_scoped_company_name(company_name, scope)
        if match["status"] == "resolved":
            company_id = str(match["company_id"])
            if company_id not in resolved_ids:
                resolved_ids.append(company_id)
            resolved_matches.append(match)
        elif match["status"] == "ambiguous":
            ambiguous_matches.append(match)
        else:
            not_found.append({"input": company_name, "reason": "no scoped HubSpot target-account match"})

    return {
        "company_ids": resolved_ids,
        "resolved_matches": resolved_matches,
        "ambiguous_matches": ambiguous_matches,
        "not_found": not_found,
        "input_count": len(refs or []),
        "processed_count": len(selected_refs),
        "truncated": len(refs or []) > limit,
    }


def _company_search(
    filters: list[dict[str, Any]],
    limit: int = 20,
    after: str | None = None,
    maximum: int = HUBSPOT_SEARCH_RESULT_LIMIT,
    sorts: list[dict[str, str]] | None = None,
    query: str | None = None,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=maximum)
    cleaned_query = str(query or "").strip()
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = after

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": COMPANY_PROPERTIES,
            "limit": page_limit,
            "sorts": sorts or [{"propertyName": "notes_last_updated", "direction": "DESCENDING"}],
        }
        if cleaned_query:
            body["query"] = cleaned_query
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


def _hubspot_date_filter_value(value: date) -> str:
    return str(int(datetime.combine(value, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000))


def _company_search_by_renewal_window(
    countries: list[str],
    owner_id: str | None,
    start_date: date,
    end_date: date,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    merged: dict[str, dict[str, Any]] = {}
    source_totals: dict[str, int | None] = {}
    source_returned_counts: dict[str, int] = {}
    source_truncated = False
    start_value = _hubspot_date_filter_value(start_date)
    end_value = _hubspot_date_filter_value(end_date)

    for property_name in RENEWAL_DATE_PROPERTIES:
        filters = [
            *_target_filters(countries, owner_id),
            {"propertyName": property_name, "operator": "GTE", "value": start_value},
            {"propertyName": property_name, "operator": "LTE", "value": end_value},
        ]
        data = _company_search(
            filters,
            requested_limit,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
            sorts=[{"propertyName": property_name, "direction": "ASCENDING"}],
        )
        source_totals[property_name] = data.get("total")
        source_returned_counts[property_name] = data.get("returned_count", len(data.get("results", [])))
        source_truncated = source_truncated or bool(data.get("truncated"))

        for company in data.get("results", []):
            company_id = str(company.get("id") or "")
            if not company_id:
                continue
            if company_id not in merged:
                copied = dict(company)
                copied["_renewal_match_fields"] = []
                merged[company_id] = copied
            match_fields = merged[company_id].setdefault("_renewal_match_fields", [])
            if property_name not in match_fields:
                match_fields.append(property_name)

    results = list(merged.values())
    returned_results = results[:requested_limit]
    has_more = source_truncated or len(results) > requested_limit
    return {
        "results": returned_results,
        "total": None if has_more else len(results),
        "requested_limit": requested_limit,
        "returned_count": len(returned_results),
        "has_more": has_more,
        "truncated": has_more,
        "source_totals": source_totals,
        "source_returned_counts": source_returned_counts,
    }


def _company_search_missing_renewal_dates(
    countries: list[str],
    owner_id: str | None,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
    filters = [
        *_target_filters(countries, owner_id),
        {"propertyName": RENEWAL_SOURCE_OF_TRUTH_PROPERTY, "operator": "NOT_HAS_PROPERTY"},
    ]
    return _company_search(filters, requested_limit, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)


def _task_search(
    filters: list[dict[str, Any]],
    limit: int = 50,
    after: str | None = None,
    maximum: int = TASK_SEARCH_RESULT_LIMIT,
) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=maximum)
    results: list[dict[str, Any]] = []
    total: int | None = None
    next_after = after

    while len(results) < requested_limit:
        page_limit = min(HUBSPOT_SEARCH_PAGE_LIMIT, requested_limit - len(results))
        body: dict[str, Any] = {
            "filterGroups": [{"filters": filters}],
            "properties": TASK_PROPERTIES,
            "limit": page_limit,
            "sorts": [{"propertyName": "hs_timestamp", "direction": "ASCENDING"}],
        }
        if next_after:
            body["after"] = next_after

        page = _post("/crm/v3/objects/tasks/search", body)
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


def _task_datetime_filter_value(value: str, end_of_day: bool = False) -> str:
    parsed = _date_value(value)
    if not parsed:
        return value
    if "T" in value:
        return value
    suffix = "T23:59:59Z" if end_of_day else "T00:00:00Z"
    return f"{parsed.isoformat()}{suffix}"


def _task_search_filters(owner_id: str | None = None, due_start: str = "", due_end: str = "") -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_task_status", "operator": "NEQ", "value": "COMPLETED"},
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id})
    if due_start:
        filters.append(
            {"propertyName": "hs_timestamp", "operator": "GTE", "value": _task_datetime_filter_value(due_start)}
        )
    if due_end:
        filters.append(
            {"propertyName": "hs_timestamp", "operator": "LTE", "value": _task_datetime_filter_value(due_end, True)}
        )
    return filters


def _target_filters(countries: list[str], owner_id: str | None = None) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = [
        {"propertyName": "hs_is_target_account", "operator": "EQ", "value": "true"},
        {"propertyName": "company_country", "operator": "IN", "values": countries},
    ]
    if owner_id:
        filters.append({"propertyName": "hubspot_owner_id", "operator": "EQ", "value": owner_id})
    return filters


def _normalize_domain_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.split("/")[0]


def _normalize_company_name_key(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    if not text or len(text) < 3 or len(text) > 80:
        return ""
    return text


def _unique_values(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _add_luma_candidate(
    candidates: dict[str, dict[str, Any]],
    company: dict[str, Any],
    match_reason: str,
    match_key: str,
    confidence: str,
) -> None:
    company_id = str(company.get("id") or "")
    if not company_id:
        return
    summary = candidates.setdefault(company_id, _summarize_company(company))
    reasons = summary.setdefault("luma_match_reasons", [])
    if match_reason not in reasons:
        reasons.append(match_reason)
    keys = summary.setdefault("luma_match_keys", [])
    key_entry = {"kind": match_reason, "value": match_key}
    if key_entry not in keys:
        keys.append(key_entry)
    if confidence == "needs-check":
        summary["luma_match_confidence"] = "needs-check"
    else:
        summary.setdefault("luma_match_confidence", "verified")


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


def _account_status_from_props(props: dict[str, Any]) -> dict[str, str]:
    company_type = str(props.get("type") or "").strip().upper()
    lifecycle_stage = str(props.get("lifecyclestage") or "").strip().lower()
    prospecting = str(props.get("prospecting_account") or "").strip().lower()
    if company_type == "CUSTOMER" or lifecycle_stage == "customer":
        return {
            "account_status": "customer",
            "account_status_source": "HubSpot company type=CUSTOMER or lifecyclestage=customer",
        }
    if company_type == "PROSPECT":
        return {
            "account_status": "prospect",
            "account_status_source": "HubSpot company type=PROSPECT",
        }
    if lifecycle_stage in {"subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead", "opportunity"}:
        return {
            "account_status": "prospect",
            "account_status_source": f"HubSpot company lifecyclestage={lifecycle_stage}",
        }
    if prospecting == "true":
        return {
            "account_status": "prospect",
            "account_status_source": "HubSpot company prospecting_account=true",
        }
    return {
        "account_status": "unknown",
        "account_status_source": "HubSpot company type/lifecyclestage/prospecting_account did not classify customer vs prospect",
    }


def _c360_company_url_template() -> str:
    return os.environ.get(C360_COMPANY_URL_TEMPLATE_ENV, "").strip() or DEFAULT_C360_COMPANY_URL_TEMPLATE


def _c360_org_url_template() -> str:
    return os.environ.get(C360_ORG_URL_TEMPLATE_ENV, "").strip() or DEFAULT_C360_ORG_URL_TEMPLATE


def _c360_route_key_map() -> dict[str, str]:
    mappings = dict(DEFAULT_C360_ROUTE_KEY_BY_COMPANY_ID)
    raw = os.environ.get(C360_ROUTE_KEY_BY_COMPANY_ID_ENV, "").strip()
    if not raw:
        return mappings
    try:
        configured = json.loads(raw)
    except json.JSONDecodeError:
        return mappings
    if not isinstance(configured, dict):
        return mappings
    for company_id, route_key in configured.items():
        company_id_text = str(company_id or "").strip()
        route_key_text = str(route_key or "").strip()
        if company_id_text and route_key_text:
            mappings[company_id_text] = route_key_text
    return mappings


def _customer360_route_key(
    hubspot_company_id: Any,
    company_name: Any = "",
    customer360_route_key: Any = "",
) -> str:
    explicit_route_key = str(customer360_route_key or "").strip()
    if explicit_route_key:
        return explicit_route_key

    company_id = str(hubspot_company_id or "").strip()
    if not company_id:
        return ""

    mapped_route_key = _c360_route_key_map().get(company_id)
    if mapped_route_key:
        return mapped_route_key

    if not company_id.isdigit():
        return company_id

    return ""


def _encode_url_value(value: Any) -> str:
    return urllib.parse.quote(str(value or "").strip(), safe="")


def _render_c360_url(
    hubspot_company_id: Any,
    organisation_id: Any = "",
    customer360_route_key: Any = "",
    company_name: Any = "",
) -> str:
    company_id = str(hubspot_company_id or "").strip()
    org_id = str(organisation_id or "").strip()
    route_key = _customer360_route_key(company_id, company_name, customer360_route_key)
    if not route_key:
        return ""

    values = {
        "customer360_route_key": _encode_url_value(route_key),
        "hubspot_company_id": _encode_url_value(route_key),
        "hubspot_numeric_company_id": _encode_url_value(company_id),
        "organisation_id": _encode_url_value(org_id),
    }
    template = _c360_org_url_template() if org_id else _c360_company_url_template()
    return template.format(**values)


def _decision_maker_count_source(props: dict[str, Any]) -> dict[str, str]:
    return {
        "decision_maker_count_source": (
            "HubSpot company property hs_num_decision_makers: HubSpot count of associated contacts with buying role DECISION_MAKER."
        ),
        "buying_role_contact_count_source": (
            "HubSpot company property hs_num_contacts_with_buying_roles: HubSpot count of associated contacts with any buying role."
        ),
        "eazybe_note": (
            "NurtureAny does not read Eazybe directly for this count; if Eazybe updates HubSpot contact buying roles, that is upstream HubSpot data hygiene."
        ),
    }


def _has_decision_maker_buying_role(value: Any) -> bool:
    roles = re.split(r"[;,]", str(value or ""))
    return any(role.strip().upper() == "DECISION_MAKER" for role in roles)


def _contact_role_text(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return str(contact.get("persona") or props.get("job_role") or props.get("jobtitle") or "")


def _contact_buying_role_text(contact: dict[str, Any]) -> str:
    props = contact.get("properties", {})
    return str(contact.get("buying_role") or props.get("hs_buying_role") or "")


def _decision_maker_coverage(
    props: dict[str, Any],
    contacts: list[dict[str, Any]] | None = None,
    contact_count: int | None = None,
) -> dict[str, Any]:
    safe_contacts = contacts or []
    associated_contact_count = len(safe_contacts) if contact_count is None and contacts is not None else contact_count
    hubspot_direct_count = _int_value(props.get("hs_num_decision_makers"))
    buying_role_contact_count = _int_value(props.get("hs_num_contacts_with_buying_roles"))
    verified_contacts = [
        contact
        for contact in safe_contacts
        if contact.get("is_verified_decision_maker") or _has_decision_maker_buying_role(_contact_buying_role_text(contact))
    ]
    role_candidates = [
        contact
        for contact in safe_contacts
        if not (contact.get("is_verified_decision_maker") or _has_decision_maker_buying_role(_contact_buying_role_text(contact)))
        and (contact.get("is_role_inferred_decision_maker") or _role_is_decision_maker(_contact_role_text(contact)))
    ]
    verified_count = max(hubspot_direct_count, len(verified_contacts))
    issues: list[str] = []
    if associated_contact_count == 0 and verified_count > 0:
        issues.append("company_rollup_has_decision_maker_but_no_associated_contact_returned")
    if buying_role_contact_count > 0 and verified_count == 0:
        issues.append("buying_role_contacts_exist_but_none_are_decision_maker")

    if issues:
        status = "needs-check"
    elif verified_count > 0:
        status = "verified"
    elif role_candidates:
        status = "needs-check"
    else:
        status = "missing"

    return {
        "associated_contact_count": associated_contact_count if associated_contact_count is not None else None,
        "verified_decision_maker_count": verified_count,
        "decision_maker_count": verified_count,
        "decision_maker_count_from_hubspot_property": hubspot_direct_count,
        "decision_maker_count_from_contact_buying_role": len(verified_contacts),
        "buying_role_contact_count": buying_role_contact_count,
        "role_inferred_decision_maker_candidate_count": len(role_candidates),
        "status": status,
        "confidence": "verified" if status == "verified" else "needs-check",
        "issues": issues,
        "sources": _decision_maker_count_source(props),
    }


def _calendar_scan_instruction(company_summary: dict[str, Any]) -> dict[str, Any]:
    owner_email = _normalize_email(str(company_summary.get("owner_email") or ""))
    if owner_email:
        calendar_ids = [owner_email]
        confidence = "verified"
        caveat = "Scan the HubSpot company owner's calendar through the team@staffany.com OAuth account."
    else:
        calendar_ids = []
        confidence = "blocked"
        caveat = "HubSpot owner email is missing, so AE calendar coverage cannot be scanned reliably."
    return {
        "calendar_account_email": "team@staffany.com",
        "calendar_ids": calendar_ids,
        "owner_email": owner_email,
        "owner_name": company_summary.get("owner_name") or "",
        "confidence": confidence,
        "caveat": caveat,
    }


def _calendar_audit_contact(contact: dict[str, Any]) -> dict[str, Any]:
    safe = _safe_contact(contact)
    props = contact.get("properties", {})
    email = _normalize_email(str(props.get("email") or ""))
    return {
        "contact_id": safe.get("contact_id"),
        "display_name": safe.get("display_name"),
        "persona": safe.get("persona"),
        "buying_role": safe.get("buying_role"),
        "is_verified_decision_maker": safe.get("is_verified_decision_maker"),
        "is_role_inferred_decision_maker": safe.get("is_role_inferred_decision_maker"),
        "decision_maker_confidence": safe.get("decision_maker_confidence"),
        "email_domain": _email_domain(email),
        "email_hash": _hash_email(email),
    }


def _calendar_audit_readiness(company_summary: dict[str, Any]) -> dict[str, str]:
    missing = set(company_summary.get("missing_fields") or [])
    decision_coverage = company_summary.get("decision_maker_coverage") or {}
    return {
        "authority": str(decision_coverage.get("status") or "needs-check"),
        "current_tools": "missing" if "current tools" in missing else "verified",
        "timeline": "missing" if "contract end date" in missing else "verified",
        "stakeholder_map": "missing" if "associated contact" in missing else "verified",
        "need": "needs-check",
    }


def _calendar_audit_seed(company_summary: dict[str, Any], contacts: list[dict[str, Any]]) -> dict[str, Any]:
    clean_lead_field_labels = {
        "industry": "industry",
        "headcount": "headcount",
        "current tools": "current tools",
        "current_tools": "current tools",
        "contract end date": "contract end date",
        "contract_end_date": "contract end date",
        "associated contact": "associated contact",
        "associated_contact": "associated contact",
        "decision maker": "verified decision maker",
        "verified_decision_maker": "verified decision maker",
    }
    missing_clean_lead_fields: list[str] = []
    for field in company_summary.get("missing_fields", []):
        label = clean_lead_field_labels.get(field)
        if label and label not in missing_clean_lead_fields:
            missing_clean_lead_fields.append(label)
    return {
        "company_id": company_summary.get("company_id"),
        "company_name": company_summary.get("name") or "",
        "company_domain": _clean_domain(str(company_summary.get("domain") or "")),
        "owner_email": company_summary.get("owner_email") or "",
        "owner_name": company_summary.get("owner_name") or "",
        "calendar_account_email": "team@staffany.com",
        "calendar_ids": list((company_summary.get("calendar_scan_instruction") or {}).get("calendar_ids") or []),
        "missing_clean_lead_fields": missing_clean_lead_fields,
        "decision_maker_coverage": company_summary.get("decision_maker_coverage") or {},
        "ic_bant_readiness": _calendar_audit_readiness(company_summary),
        "contact_match_records": [_calendar_audit_contact(contact) for contact in contacts],
        "privacy": "Email hashes/domains only; raw HubSpot contact emails are not returned.",
    }


def _summarize_company(company: dict[str, Any]) -> dict[str, Any]:
    props = company.get("properties", {})
    decision_coverage = _decision_maker_coverage(props)
    contract_date = props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY) or ""
    owner_id = props.get("hubspot_owner_id") or ""
    company_id = company.get("id")
    account_status = _account_status_from_props(props)
    customer360_route_key = _customer360_route_key(
        company_id,
        props.get("name") or "",
        props.get("customer360_route_key") or props.get("customer_slug") or "",
    )
    c360_url = (
        _render_c360_url(company_id, customer360_route_key=customer360_route_key, company_name=props.get("name") or "")
        if account_status["account_status"] == "customer"
        else ""
    )
    owner = {
        "owner_id": owner_id,
        "owner_email": _owner_email_by_id(owner_id),
        "owner_name": _owner_name_by_id(owner_id),
    }
    summary = {
        "company_id": company_id,
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": props.get("name") or "",
        "domain": props.get("domain") or "",
        "country": props.get("company_country") or "",
        **owner,
        "headcount": props.get("numberofemployees") or "",
        "industry": props.get("industry") or "",
        "company_type": props.get("type") or "",
        "lifecycle_stage": props.get("lifecyclestage") or "",
        **account_status,
        "contract_end_date": props.get("contract_end_date") or "",
        "current_tool_renewal_date": props.get("current_tool_renewal_date") or "",
        "current_tools": props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY) or "",
        "contract_or_renewal_date": contract_date,
        "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
        "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
        "last_activity_at": props.get("notes_last_updated") or "",
        "decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "verified_decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "buying_role_contact_count": decision_coverage["buying_role_contact_count"],
        "role_inferred_decision_maker_candidate_count": decision_coverage["role_inferred_decision_maker_candidate_count"],
        "decision_maker_coverage": decision_coverage,
        **_decision_maker_count_source(props),
        "prospecting_account": props.get("prospecting_account") or "",
        "enrichment_status": _enrichment_status(props, contact_count=None),
        "missing_fields": _missing_company_fields(props, contact_count=None),
    }
    if c360_url:
        summary["c360_url"] = c360_url
        summary["customer360_url"] = c360_url
        summary["customer360_route_key"] = customer360_route_key
    elif account_status["account_status"] == "customer":
        summary["c360_link_status"] = "needs-route-key"
        summary["c360_link_caveat"] = "C360 link missing because Customer 360 route key was unavailable."
    return summary


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


def _datetime_value(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        parsed_date = _date_value(text)
        if not parsed_date:
            return None
        parsed = datetime.combine(parsed_date, datetime.min.time(), tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _unique_text(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        key = text.lower()
        if text and key not in seen:
            seen.add(key)
            output.append(text)
    return output


def _normalized_words(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _text_contains_term(text: str, term: str) -> bool:
    normalized_text = f" {_normalized_words(text)} "
    normalized_term = _normalized_words(term)
    if not normalized_text.strip() or not normalized_term:
        return False
    return f" {normalized_term} " in normalized_text or normalized_term in normalized_text


def _clean_domain(domain: str) -> str:
    text = str(domain or "").strip().lower()
    for prefix in ("https://", "http://"):
        if text.startswith(prefix):
            text = text[len(prefix) :]
    return text.split("/")[0].strip()


def _email_domain(email: str) -> str:
    normalized = _normalize_email(email)
    if "@" not in normalized:
        return ""
    return _clean_domain(normalized.rsplit("@", 1)[1])


def _hash_email(email: str) -> str:
    normalized = _normalize_email(email)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16] if normalized else ""


def _canonical_event_type(value: str) -> str:
    words = _normalized_words(value)
    if not words:
        return ""
    for alias, display in EVENT_TYPE_ALIASES.items():
        if words == alias or alias in words:
            return display
    return ""


def _canonical_location(value: str) -> str:
    words = _normalized_words(value)
    if not words:
        return ""
    for alias, display in LOCATION_ALIASES.items():
        if words == alias or alias in words:
            return display
    return ""


def _canonical_country(value: str) -> str:
    text = str(value or "")
    words = _normalized_words(text)
    tokens = set(words.split())
    if not words:
        return ""
    if "singapore" in words or "sg" in tokens or "asia singapore" in words:
        return "Singapore"
    if "indonesia" in words or "jakarta" in words or "bali" in words or "jkt" in tokens:
        return "Indonesia"
    if "malaysia" in words or "kuala lumpur" in words or "kl" in tokens:
        return "Malaysia"
    return ""


def _resolved_event_filters(country: str, event_type: str, location: str) -> dict[str, str]:
    location_filter = _canonical_location(location) or _canonical_location(event_type) or _canonical_location(country)
    event_type_filter = _canonical_event_type(event_type)
    country_filter = _canonical_country(country)
    if not country_filter and location_filter:
        country_filter = LOCATION_COUNTRY_MAP.get(location_filter, "")
    return {"country": country_filter, "event_type": event_type_filter, "location": location_filter}


def _event_tag_filters(event_tags: Any, country: str = "", event_type: str = "", location: str = "") -> list[str]:
    raw: list[Any] = []
    if isinstance(event_tags, str):
        raw.extend(part.strip() for part in re.split(r"[,;]", event_tags) if part.strip())
    elif isinstance(event_tags, list):
        raw.extend(event_tags)
    tags: list[str] = []
    for value in raw:
        text = str(value or "").strip()
        if text:
            tags.append(_canonical_location(text) or _canonical_event_type(text) or _canonical_country(text) or text)
    filters = _resolved_event_filters(country, event_type, location)
    if filters["location"]:
        tags.append(filters["location"])
    if filters["event_type"]:
        tags.append(filters["event_type"])
    return _unique_text(tags)


def _luma_entries(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("entries", "items", "events", "guests", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _luma_has_more(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return bool(payload.get("has_more") or payload.get("hasMore") or pagination.get("has_more"))


def _luma_next_cursor(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    pagination = payload.get("pagination") if isinstance(payload.get("pagination"), dict) else {}
    return str(payload.get("next_cursor") or payload.get("nextCursor") or pagination.get("next_cursor") or "").strip()


def _luma_event_payload(item: dict[str, Any]) -> dict[str, Any]:
    event = item.get("event")
    return event if isinstance(event, dict) else item


def _luma_guest_payload(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("guest", "event_guest", "eventGuest"):
        guest = item.get(key)
        if isinstance(guest, dict):
            merged = dict(guest)
            for outer_key in ("approval_status", "checked_in_at", "registered_at", "created_at"):
                if outer_key in item and outer_key not in merged:
                    merged[outer_key] = item[outer_key]
            return merged
    return item


def _luma_event_id(event: dict[str, Any]) -> str:
    return str(event.get("event_id") or event.get("api_id") or event.get("id") or "").strip()


def _luma_event_metadata_text(event: dict[str, Any]) -> str:
    fields = [
        str(event.get("name") or event.get("title") or ""),
        str(event.get("url") or event.get("event_url") or event.get("eventUrl") or ""),
        str(event.get("timezone") or ""),
    ]
    location = event.get("geo_address_json") or event.get("address") or event.get("location")
    if isinstance(location, (dict, list)):
        fields.append(json.dumps(location, sort_keys=True))
    elif location:
        fields.append(str(location))
    return " ".join(field for field in fields if field)


def _luma_event_tag_names(event: dict[str, Any]) -> list[str]:
    raw_tags: list[Any] = []
    for field in ("event_tags", "eventTags", "tags", "tag_ids", "tagIds"):
        value = event.get(field)
        if isinstance(value, list):
            raw_tags.extend(value)
        elif value:
            raw_tags.append(value)
    names: list[str] = []
    for tag in raw_tags:
        if isinstance(tag, str):
            names.append(tag)
        elif isinstance(tag, dict):
            names.append(str(tag.get("name") or tag.get("title") or tag.get("api_id") or tag.get("id") or "").strip())
    return _unique_text(names)


def _inferred_luma_tags(event: dict[str, Any]) -> list[str]:
    text = _luma_event_metadata_text(event)
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


def _safe_luma_event(item: dict[str, Any]) -> dict[str, Any]:
    event = _luma_event_payload(item)
    luma_tags = _luma_event_tag_names(event)
    inferred_tags = _inferred_luma_tags(event)
    classifiable_tags = _unique_text(luma_tags + inferred_tags)
    location_tags = _unique_text([location for tag in classifiable_tags if (location := _canonical_location(tag))])
    country_tags = _unique_text([country for tag in classifiable_tags if (country := _canonical_country(tag))])
    event_type_tags = _unique_text([event_type for tag in classifiable_tags if (event_type := _canonical_event_type(tag))])
    return {
        "event_id": _luma_event_id(event),
        "name": event.get("name") or event.get("title") or "",
        "start_at": event.get("start_at") or event.get("startAt") or "",
        "end_at": event.get("end_at") or event.get("endAt") or "",
        "timezone": event.get("timezone") or "",
        "url": event.get("url") or event.get("event_url") or event.get("eventUrl") or "",
        "tags": luma_tags or inferred_tags,
        "location_tags": location_tags,
        "country_tags": country_tags,
        "event_type_tags": event_type_tags,
        "tag_match_source": "luma_event_tags" if luma_tags else ("inferred_from_event_metadata" if inferred_tags else "none"),
    }


def _event_matches_filters(event: dict[str, Any], query: str, country: str, event_type: str, location: str, event_tags: Any) -> bool:
    haystack_values = [str(event.get(key) or "") for key in ("name", "url", "event_id")]
    for key in ("tags", "location_tags", "country_tags", "event_type_tags"):
        value = event.get(key)
        if isinstance(value, list):
            haystack_values.extend(str(item) for item in value)
    haystack = " ".join(haystack_values).lower()
    if query.strip() and query.strip().lower() not in haystack:
        return False
    requested_tags = _event_tag_filters(event_tags, country, event_type, location)
    if requested_tags:
        event_tag_set = {str(tag).strip().lower() for tag in event.get("tags", []) if str(tag or "").strip()}
        if not all(tag.lower() in event_tag_set for tag in requested_tags):
            return False
    filters = _resolved_event_filters(country, event_type, location)
    if filters["location"] and filters["location"] not in event.get("location_tags", []):
        return False
    if filters["country"] and filters["country"] not in event.get("country_tags", []):
        return False
    if filters["event_type"] and filters["event_type"] not in event.get("event_type_tags", []):
        return False
    return True


def _rfc3339_or_default(value: str, default: datetime) -> str:
    text = str(value or "").strip()
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


def _list_luma_events_for_followup(
    query: str,
    start: str,
    end: str,
    country: str,
    event_type: str,
    location: str,
    event_tags: Any,
) -> tuple[list[dict[str, Any]], bool, bool]:
    now = datetime.now(timezone.utc)
    after = _rfc3339_or_default(start, now - timedelta(days=LUMA_EVENT_LOOKBACK_DAYS))
    before = _rfc3339_or_default(end, now + timedelta(days=LUMA_EVENT_LOOKAHEAD_DAYS))
    events: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    while len(events) < LUMA_MAX_EVENTS_FOR_FOLLOWUP:
        payload = _luma_request_json(
            "/v1/calendar/list-events",
            {
                "after": after,
                "before": before,
                "pagination_cursor": cursor,
                "pagination_limit": LUMA_PAGE_LIMIT,
                "sort_column": "start_at",
                "sort_direction": "asc",
                "status": "approved",
            },
        )
        page_events = [_safe_luma_event(item) for item in _luma_entries(payload)]
        events.extend(event for event in page_events if _event_matches_filters(event, query, country, event_type, location, event_tags))
        has_more = _luma_has_more(payload)
        cursor = _luma_next_cursor(payload)
        if not has_more or not cursor:
            break
    truncated = len(events) > LUMA_MAX_EVENTS_FOR_FOLLOWUP or (has_more and len(events) >= LUMA_MAX_EVENTS_FOR_FOLLOWUP)
    return events[:LUMA_MAX_EVENTS_FOR_FOLLOWUP], has_more, truncated


def _single_luma_event(event_id: str) -> dict[str, Any]:
    try:
        payload = _luma_request_json("/v1/event/get", {"id": event_id})
    except LumaEventError as error:
        if error.status_code != 400:
            raise
        payload = _luma_request_json("/v1/event/get", {"event_id": event_id})
    event = _safe_luma_event(payload)
    if not event["event_id"]:
        event["event_id"] = event_id
    return event


def _latest_luma_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not events:
        return None
    now = datetime.now(timezone.utc)
    past_events = [event for event in events if (_datetime_value(str(event.get("start_at") or "")) or now) <= now]
    candidates = past_events or events
    return sorted(
        candidates,
        key=lambda event: _datetime_value(str(event.get("start_at") or "")) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[0]


def _luma_checked_in_at(guest: dict[str, Any]) -> str:
    return str(guest.get("checked_in_at") or guest.get("checkedInAt") or "").strip()


def _luma_guest_email(guest: dict[str, Any]) -> str:
    return _normalize_email(str(guest.get("email") or guest.get("guest_email") or guest.get("email_address") or ""))


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


def _luma_guest_company_candidates(guest: dict[str, Any]) -> list[str]:
    fields = [
        str(guest.get("company") or ""),
        str(guest.get("company_name") or guest.get("companyName") or ""),
        str(guest.get("organization") or guest.get("organisation") or ""),
    ]
    fields.extend(_registration_texts(guest.get("registration_answers")))
    fields.extend(_registration_texts(guest.get("registrationAnswers")))
    return _unique_text([field for field in fields if field.strip()])


def _list_luma_guests(event_id: str, max_guests: int = LUMA_MAX_GUESTS_PER_EVENT) -> tuple[list[dict[str, Any]], bool, bool]:
    limit = max(1, min(int(max_guests or LUMA_MAX_GUESTS_PER_EVENT), LUMA_MAX_GUESTS_PER_EVENT))
    guests: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    while len(guests) < limit:
        page_limit = min(LUMA_PAGE_LIMIT, limit - len(guests))
        payload = _luma_request_json(
            "/v1/event/get-guests",
            {
                "event_id": event_id,
                "pagination_cursor": cursor,
                "pagination_limit": page_limit,
                "sort_column": "registered_at",
                "sort_direction": "asc",
            },
        )
        guests.extend(_luma_guest_payload(item) for item in _luma_entries(payload))
        has_more = _luma_has_more(payload)
        cursor = _luma_next_cursor(payload)
        if not has_more or not cursor:
            break
    truncated = has_more and len(guests) >= limit
    return guests[:limit], has_more, truncated


def _renewal_matches_in_window(company: dict[str, Any], start_date: date, end_date: date) -> list[dict[str, Any]]:
    props = company.get("properties", {})
    matches: list[dict[str, Any]] = []
    for property_name in RENEWAL_DATE_PROPERTIES:
        raw_value = str(props.get(property_name) or "")
        parsed = _date_value(raw_value)
        if parsed and start_date <= parsed <= end_date:
            matches.append(
                {
                    "property_name": property_name,
                    "value": raw_value,
                    "date": parsed,
                }
            )
    return sorted(
        matches,
        key=lambda item: (
            item["date"],
            RENEWAL_DATE_PROPERTIES.index(str(item["property_name"])),
        ),
    )


def _contact_detail_missing_fields(contacts: list[dict[str, Any]]) -> list[str]:
    if not contacts:
        return []
    missing: list[str] = []
    if not any(contact.get("persona") for contact in contacts):
        missing.append("persona")
    if not any(contact.get("channel_fit") for contact in contacts):
        missing.append("channel fit")
    return missing


def _missing_company_fields(
    props: dict[str, Any],
    contact_count: int | None,
    contacts: list[dict[str, Any]] | None = None,
) -> list[str]:
    missing: list[str] = []
    if not props.get("hubspot_owner_id"):
        missing.append("company owner")
    if not props.get("company_country"):
        missing.append("country")
    if not props.get("numberofemployees"):
        missing.append("headcount")
    if not props.get("industry"):
        missing.append("industry")
    if not props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("contract end date")
    if not props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("current tools")
    if contact_count == 0:
        missing.append("associated contact")
    coverage = _decision_maker_coverage(props, contacts, contact_count)
    if coverage["verified_decision_maker_count"] < 1:
        missing.append("decision maker")
    return missing


def _enrichment_status(
    props: dict[str, Any],
    contact_count: int | None,
    contacts: list[dict[str, Any]] | None = None,
) -> str:
    missing = _missing_company_fields(props, contact_count, contacts)
    if missing:
        return "not_enriched"
    if contacts is not None and _contact_detail_missing_fields(contacts):
        return "minimum_enriched"
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
    results: list[dict[str, Any]] = []
    for index in range(0, len(ids), 100):
        chunk = ids[index : index + 100]
        data = _post(
            f"/crm/v3/objects/{object_type}/batch/read",
            {
                "properties": properties,
                "inputs": [{"id": object_id} for object_id in chunk],
            },
        )
        results.extend(data.get("results", []))
    return results


def _batch_association_ids(from_type: str, to_type: str, ids: list[str]) -> dict[str, list[str]]:
    if not ids:
        return {}
    associations: dict[str, list[str]] = {}
    for index in range(0, len(ids), 100):
        chunk = ids[index : index + 100]
        data = _post(
            f"/crm/v4/associations/{from_type}/{to_type}/batch/read",
            {"inputs": [{"id": object_id} for object_id in chunk]},
        )
        for object_id in chunk:
            associations.setdefault(str(object_id), [])
        for result in data.get("results", []):
            from_id = str(result.get("from", {}).get("id") or "")
            if not from_id:
                continue
            associations.setdefault(from_id, [])
            for target in result.get("to", []):
                to_id = str(target.get("toObjectId") or "")
                if to_id and to_id not in associations[from_id]:
                    associations[from_id].append(to_id)
    return associations


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


def _add_activity_sources(
    activity_sources: dict[str, list[dict[str, str]]],
    activity_ids: list[str],
    source_type: str,
    source_id: str,
) -> None:
    for activity_id in activity_ids:
        sources = activity_sources.setdefault(activity_id, [])
        source = {"object_type": source_type, "object_id": str(source_id)}
        if source not in sources:
            sources.append(source)


def _collect_activity_associations(
    company_id: str,
    contact_ids: list[str],
    deal_ids: list[str],
    object_type: str,
) -> dict[str, Any]:
    activity_sources: dict[str, list[dict[str, str]]] = {}
    truncated = False

    company_activities = _association_ids_with_metadata("companies", company_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
    _add_activity_sources(activity_sources, company_activities["ids"], "company", company_id)
    truncated = truncated or company_activities["truncated"]

    for contact_id in contact_ids:
        contact_activities = _association_ids_with_metadata("contacts", contact_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
        _add_activity_sources(activity_sources, contact_activities["ids"], "contact", contact_id)
        truncated = truncated or contact_activities["truncated"]

    for deal_id in deal_ids:
        deal_activities = _association_ids_with_metadata("deals", deal_id, object_type, FOLLOWUP_ASSOCIATION_LIMIT)
        _add_activity_sources(activity_sources, deal_activities["ids"], "deal", deal_id)
        truncated = truncated or deal_activities["truncated"]

    return {
        "activity_ids": list(activity_sources.keys()),
        "activity_sources": activity_sources,
        "truncated": truncated,
    }


def _activity_timestamp(activity: dict[str, Any]) -> str:
    props = activity.get("properties", {})
    return str(props.get("hs_timestamp") or props.get("hs_lastmodifieddate") or "")


def _is_activity_in_window(activity: dict[str, Any], since_dt: datetime, until_dt: datetime | None) -> bool:
    timestamp = _datetime_value(_activity_timestamp(activity))
    if not timestamp:
        return False
    if timestamp < since_dt:
        return False
    if until_dt and timestamp > until_dt:
        return False
    return True


def _is_whatsapp_communication(activity: dict[str, Any]) -> bool:
    props = activity.get("properties", {})
    channel = str(props.get("hs_communication_channel_type") or "").strip().upper().replace("-", "_").replace(" ", "_")
    return channel in {"WHATS_APP", "WHATSAPP"}


def _event_followup_terms(event_context: dict[str, Any] | None) -> list[str]:
    if not event_context:
        return []
    raw_terms: list[Any] = []
    event = event_context.get("event") if isinstance(event_context.get("event"), dict) else {}
    raw_terms.append(event.get("name"))
    for key in ("tags", "location_tags", "event_type_tags"):
        value = event.get(key)
        if isinstance(value, list):
            raw_terms.extend(value)
    raw_terms.extend(event_context.get("event_tags") or [])
    for term in list(raw_terms):
        canonical = _canonical_event_type(str(term)) or _canonical_location(str(term))
        if canonical:
            raw_terms.append(canonical)
    if any(_canonical_event_type(str(term)) == "HR Happy Hour" for term in raw_terms):
        raw_terms.extend(["HHH", "HR Happy Hour", "Happy Hour"])
    if any(_canonical_event_type(str(term)) == "Leaders Lounge" for term in raw_terms):
        raw_terms.extend(["LL", "Leaders Lounge"])
    blocked = {"staffany", "singapore", "malaysia", "indonesia"}
    terms = [
        term
        for term in _unique_text(raw_terms)
        if len(_normalized_words(term)) >= 3 and _normalized_words(term) not in blocked
    ]
    return terms


def _event_specific_match(
    evidence_type: str,
    activity: dict[str, Any],
    event_context: dict[str, Any] | None,
) -> dict[str, str]:
    if not event_context:
        return {"event_match": "not_checked", "match_reason": ""}
    props = activity.get("properties", {})
    if evidence_type == "communication":
        text = str(props.get("hs_communication_body") or "")
    elif evidence_type == "task":
        text = str(props.get("hs_task_subject") or "")
    else:
        return {"event_match": "weak", "match_reason": "event_body_not_read"}
    event_terms = _event_followup_terms(event_context)
    has_event_term = any(_text_contains_term(text, term) for term in event_terms)
    has_followup_phrase = any(_text_contains_term(text, phrase) for phrase in EVENT_FOLLOWUP_PHRASES)
    strong_followup_phrase = any(
        _text_contains_term(text, phrase)
        for phrase in ("thanks for attending", "terima kasih", "makasih", "sudah datang", "sudah hadir", "for coming", "for joining")
    )
    if has_event_term and has_followup_phrase:
        return {"event_match": "strong", "match_reason": "event_keyword_and_followup_phrase"}
    if strong_followup_phrase:
        return {"event_match": "strong", "match_reason": "event_followup_phrase"}
    if has_event_term or has_followup_phrase:
        return {"event_match": "weak", "match_reason": "partial_event_followup_signal"}
    return {"event_match": "generic", "match_reason": "no_event_followup_signal"}


def _safe_followup_evidence(
    object_type: str,
    activity: dict[str, Any],
    activity_sources: dict[str, list[dict[str, str]]],
    event_match: dict[str, str] | None = None,
) -> dict[str, Any]:
    props = activity.get("properties", {})
    object_id = str(activity.get("id") or "")
    evidence = {
        "object_type": object_type,
        "object_id": object_id,
        "timestamp": _activity_timestamp(activity),
        "owner_id": props.get("hubspot_owner_id") or "",
        "associated_via": activity_sources.get(object_id, []),
    }
    if object_type == "communication":
        evidence["channel"] = props.get("hs_communication_channel_type") or ""
        evidence["logged_from"] = props.get("hs_communication_logged_from") or ""
    if object_type == "task":
        evidence["status"] = props.get("hs_task_status") or ""
    if object_type == "meeting":
        evidence["title"] = _safe_activity_label(props.get("hs_meeting_title"))
        evidence["outcome"] = props.get("hs_meeting_outcome") or ""
        evidence["activity_type"] = _safe_activity_label(props.get("hs_activity_type"))
    if event_match:
        evidence["event_match"] = event_match.get("event_match") or ""
        evidence["match_reason"] = event_match.get("match_reason") or ""
    return evidence


def _sort_followup_evidence(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(item: dict[str, Any]) -> datetime:
        return _datetime_value(str(item.get("timestamp") or "")) or datetime.min.replace(tzinfo=timezone.utc)

    return sorted(evidence, key=key, reverse=True)


def _account_followup_status(
    company: dict[str, Any],
    contact_ids: list[str],
    deal_ids: list[str],
    since_dt: datetime,
    until_dt: datetime | None,
    event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    props = company.get("properties", {})
    company_owner_id = str(props.get("hubspot_owner_id") or "")
    counts = {
        "whatsapp_communications": 0,
        "notes": 0,
        "completed_tasks": 0,
        "open_tasks": 0,
        "completed_meetings": 0,
    }
    event_mode = event_context is not None
    if event_mode:
        counts.update(
            {
                "event_specific_whatsapp_communications": 0,
                "generic_whatsapp_communications": 0,
                "event_specific_completed_tasks": 0,
                "generic_completed_tasks": 0,
                "event_specific_open_tasks": 0,
                "generic_open_tasks": 0,
                "completed_meeting_logs": 0,
                "weak_followup_evidence": 0,
            }
        )
    evidence: list[dict[str, Any]] = []
    truncated = False
    owner_mismatch = False
    weak_evidence = False

    activity_specs = [
        ("communications", "communication", COMMUNICATION_EVENT_PROPERTIES if event_mode else COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]
    for hubspot_type, evidence_type, properties in activity_specs:
        association_data = _collect_activity_associations(company_id, contact_ids, deal_ids, hubspot_type)
        activity_ids = association_data["activity_ids"]
        read_ids = activity_ids[:FOLLOWUP_RETURN_LIMIT]
        raw_activities = _batch_read(hubspot_type, read_ids, properties)
        truncated = bool(truncated or association_data["truncated"] or len(activity_ids) > len(read_ids))

        for activity in raw_activities:
            if not _activity_timestamp(activity):
                weak_evidence = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue
            if evidence_type == "communication" and not _is_whatsapp_communication(activity):
                continue
            if evidence_type == "meeting" and not _is_completed_meeting(activity):
                continue

            event_match = _event_specific_match(evidence_type, activity, event_context) if event_mode else None
            safe_evidence = _safe_followup_evidence(evidence_type, activity, association_data["activity_sources"], event_match)
            evidence_owner_id = str(safe_evidence.get("owner_id") or "")
            if evidence_owner_id and company_owner_id and evidence_owner_id != company_owner_id:
                owner_mismatch = True

            if evidence_type == "communication":
                counts["whatsapp_communications"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_whatsapp_communications"] += 1
                elif event_mode:
                    counts["generic_whatsapp_communications"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "note":
                counts["notes"] += 1
                if event_mode:
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "meeting":
                counts["completed_meetings"] += 1
                if event_mode:
                    counts["completed_meeting_logs"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            elif _is_incomplete_task(activity):
                counts["open_tasks"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_open_tasks"] += 1
                elif event_mode:
                    counts["generic_open_tasks"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)
            else:
                counts["completed_tasks"] += 1
                if event_mode and event_match and event_match.get("event_match") == "strong":
                    counts["event_specific_completed_tasks"] += 1
                elif event_mode:
                    counts["generic_completed_tasks"] += 1
                    counts["weak_followup_evidence"] += 1
                evidence.append(safe_evidence)

    sorted_evidence = _sort_followup_evidence(evidence)
    if event_mode:
        completed_count = counts["event_specific_whatsapp_communications"] + counts["event_specific_completed_tasks"]
        weak_count = counts["weak_followup_evidence"]
        scheduled_count = counts["event_specific_open_tasks"]
    else:
        completed_count = counts["whatsapp_communications"] + counts["notes"] + counts["completed_tasks"]
        weak_count = 0
        scheduled_count = counts["open_tasks"]
    if truncated or owner_mismatch or weak_evidence:
        status = "needs_check"
    elif completed_count:
        status = "followed_up"
    elif scheduled_count:
        status = "scheduled"
    elif event_mode and weak_count:
        status = "needs_check"
    else:
        status = "not_found"

    summary = _summarize_company(company)
    return {
        "company_id": summary.get("company_id"),
        "company_name": summary.get("name"),
        "owner_id": summary.get("owner_id"),
        "country": summary.get("country"),
        "followup_status": status,
        "latest_followup_at": sorted_evidence[0]["timestamp"] if sorted_evidence else "",
        "activity_counts": counts,
        "evidence": sorted_evidence[:10],
        "activity_truncated": truncated,
        "owner_mismatch": owner_mismatch,
        "weak_evidence": weak_evidence,
        "confidence": "needs-check" if status == "needs_check" else "verified",
        "caveat": (
            "Safe HubSpot follow-up evidence only; raw WhatsApp bodies, note bodies, task bodies, phone numbers, and bulk PII are omitted."
        ),
    }


def _add_company_task_source(
    company_sources: dict[str, list[dict[str, str]]],
    company_id: str,
    source_type: str,
    source_id: str,
) -> None:
    sources = company_sources.setdefault(str(company_id), [])
    source = {"object_type": source_type, "object_id": str(source_id)}
    if source not in sources:
        sources.append(source)


def _task_company_links_for_tasks(task_ids: list[str]) -> dict[str, dict[str, Any]]:
    normalized_task_ids = [str(task_id) for task_id in task_ids if str(task_id)]
    links_by_task = {
        task_id: {"company_ids": [], "company_sources": {}, "truncated": False}
        for task_id in normalized_task_ids
    }

    direct_companies = _batch_association_ids("tasks", "companies", normalized_task_ids)
    task_contacts = _batch_association_ids("tasks", "contacts", normalized_task_ids)
    task_deals = _batch_association_ids("tasks", "deals", normalized_task_ids)

    contact_to_tasks: dict[str, list[str]] = {}
    deal_to_tasks: dict[str, list[str]] = {}

    for task_id, company_ids in direct_companies.items():
        for company_id in company_ids:
            _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "company", company_id)

    for task_id, contact_ids in task_contacts.items():
        for contact_id in contact_ids:
            contact_to_tasks.setdefault(contact_id, []).append(task_id)

    for task_id, deal_ids in task_deals.items():
        for deal_id in deal_ids:
            deal_to_tasks.setdefault(deal_id, []).append(task_id)

    contact_companies = _batch_association_ids("contacts", "companies", list(contact_to_tasks.keys()))
    for contact_id, company_ids in contact_companies.items():
        for task_id in contact_to_tasks.get(contact_id, []):
            for company_id in company_ids:
                _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "contact", contact_id)

    deal_companies = _batch_association_ids("deals", "companies", list(deal_to_tasks.keys()))
    for deal_id, company_ids in deal_companies.items():
        for task_id in deal_to_tasks.get(deal_id, []):
            for company_id in company_ids:
                _add_company_task_source(links_by_task[task_id]["company_sources"], company_id, "deal", deal_id)

    for link in links_by_task.values():
        link["company_ids"] = list(link["company_sources"].keys())

    return links_by_task


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


def _sales_followup_task_index_for_companies(
    companies: list[dict[str, Any]],
    owner_id: str | None,
    task_limit: int = TASK_SEARCH_RESULT_LIMIT,
) -> dict[str, Any]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids or not owner_id:
        return {"tasks_by_company": {}, "metadata": {}, "truncated": False}

    company_id_set = set(company_ids)
    owner_by_company = {
        str(company.get("id")): str(company.get("properties", {}).get("hubspot_owner_id") or "")
        for company in companies
        if company.get("id")
    }
    task_data = _task_search(
        _task_search_filters(owner_id),
        task_limit,
        maximum=max(TASK_SEARCH_RESULT_LIMIT, task_limit),
    )
    task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
    task_links = _task_company_links_for_tasks(task_ids)
    tasks_by_company: dict[str, list[dict[str, Any]]] = {company_id: [] for company_id in company_ids}
    association_truncated = False

    for task in task_data.get("results", []):
        task_id = str(task.get("id") or "")
        if not task_id or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        links = task_links.get(task_id, {})
        association_truncated = association_truncated or bool(links.get("truncated"))
        for company_id in links.get("company_ids", []):
            if company_id not in company_id_set:
                continue
            if task_owner_id and owner_by_company.get(company_id) != task_owner_id:
                continue
            task_summary = _safe_task_summary(
                task,
                {task_id: links.get("company_sources", {}).get(str(company_id), [])},
            )
            tasks_by_company.setdefault(company_id, []).append(task_summary)

    for company_id, tasks in tasks_by_company.items():
        tasks_by_company[company_id] = _sort_tasks_by_due_at(tasks)

    metadata = _search_metadata(task_data)
    return {
        "tasks_by_company": tasks_by_company,
        "metadata": metadata,
        "truncated": bool(metadata.get("truncated") or association_truncated),
    }


def _sales_followup_task_index_for_company_associations(
    companies: list[dict[str, Any]],
    contact_index: dict[str, list[str]],
    deal_index: dict[str, list[str]],
    task_limit: int = TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
) -> dict[str, Any]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids:
        return {
            "tasks_by_company": {},
            "metadata": {"total": 0, "requested_limit": 0, "returned_count": 0, "has_more": False, "truncated": False},
            "truncated": False,
        }

    owner_by_company = {
        str(company.get("id")): str(company.get("properties", {}).get("hubspot_owner_id") or "")
        for company in companies
        if company.get("id")
    }
    company_task_sources: dict[str, dict[str, list[dict[str, str]]]] = {company_id: {} for company_id in company_ids}

    for company_id, task_ids in _batch_association_ids("companies", "tasks", company_ids).items():
        for task_id in task_ids:
            _add_indexed_activity_source(company_task_sources, company_id, task_id, "company", company_id)

    contact_to_companies = _reverse_company_association_index(contact_index)
    for contact_id, task_ids in _batch_association_ids("contacts", "tasks", list(contact_to_companies.keys())).items():
        for company_id in contact_to_companies.get(str(contact_id), []):
            for task_id in task_ids:
                _add_indexed_activity_source(company_task_sources, company_id, task_id, "contact", contact_id)

    deal_to_companies = _reverse_company_association_index(deal_index)
    for deal_id, task_ids in _batch_association_ids("deals", "tasks", list(deal_to_companies.keys())).items():
        for company_id in deal_to_companies.get(str(deal_id), []):
            for task_id in task_ids:
                _add_indexed_activity_source(company_task_sources, company_id, task_id, "deal", deal_id)

    task_company_sources: dict[str, dict[str, list[dict[str, str]]]] = {}
    for company_id, task_sources in company_task_sources.items():
        for task_id, sources in task_sources.items():
            task_company_sources.setdefault(str(task_id), {})[str(company_id)] = sources

    task_ids = sorted(task_company_sources.keys())
    requested_limit = _bounded_int(task_limit, default=TASK_SEARCH_AIRTIGHT_RESULT_LIMIT, maximum=TASK_SEARCH_AIRTIGHT_RESULT_LIMIT)
    task_read_ids = task_ids[:requested_limit]
    raw_tasks = _batch_read("tasks", task_read_ids, TASK_PROPERTIES)
    truncated = len(task_ids) > len(task_read_ids)
    tasks_by_company: dict[str, list[dict[str, Any]]] = {company_id: [] for company_id in company_ids}

    for task in raw_tasks:
        task_id = str(task.get("id") or "")
        if not task_id or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        for company_id, sources in task_company_sources.get(task_id, {}).items():
            if task_owner_id and owner_by_company.get(company_id) != task_owner_id:
                continue
            tasks_by_company.setdefault(company_id, []).append(_safe_task_summary(task, {task_id: sources}))

    for company_id, tasks in tasks_by_company.items():
        tasks_by_company[company_id] = _sort_tasks_by_due_at(tasks)

    metadata = {
        "total": len(task_ids),
        "requested_limit": requested_limit,
        "returned_count": len(raw_tasks),
        "has_more": truncated,
        "truncated": truncated,
    }
    return {"tasks_by_company": tasks_by_company, "metadata": metadata, "truncated": truncated}


def _env_csv(name: str) -> set[str]:
    raw = os.environ.get(name, "")
    return {item.strip() for item in raw.split(",") if item.strip()}


def _warm_activity_labels() -> tuple[str, ...]:
    configured = _env_csv(WARM_ACTIVITY_LABELS_ENV_VAR)
    if configured:
        return tuple(sorted(configured, key=str.lower))
    return DEFAULT_WARM_ACTIVITY_LABELS


def _friday_review_stage_config() -> dict[str, Any]:
    pipeline_ids = _env_csv(QO_PIPELINE_IDS_ENV_VAR)
    qo_stage_ids = _env_csv(QO_STAGE_IDS_ENV_VAR)
    qo_met_stage_ids = _env_csv(QO_MET_STAGE_IDS_ENV_VAR)
    closed_won_stage_ids = _env_csv(CLOSED_WON_STAGE_IDS_ENV_VAR)
    return {
        "pipeline_ids": pipeline_ids,
        "qo_stage_ids": qo_stage_ids,
        "qo_met_stage_ids": qo_met_stage_ids,
        "closed_won_stage_ids": closed_won_stage_ids,
        "configured": bool(pipeline_ids and qo_stage_ids and qo_met_stage_ids and closed_won_stage_ids),
        "required_env": [
            QO_PIPELINE_IDS_ENV_VAR,
            QO_STAGE_IDS_ENV_VAR,
            QO_MET_STAGE_IDS_ENV_VAR,
            CLOSED_WON_STAGE_IDS_ENV_VAR,
        ],
    }


def _week_window(week_start: str = "", week_end: str = "") -> dict[str, Any]:
    local_now = datetime.now(timezone.utc).astimezone(SINGAPORE_TIMEZONE)
    default_start = local_now.date() - timedelta(days=local_now.weekday())
    default_end = default_start + timedelta(days=6)
    start_date = _date_value(week_start) or default_start
    end_date = _date_value(week_end) or default_end
    if end_date < start_date:
        raise ScopeError("week_end must be on or after week_start.")
    start_local = datetime.combine(start_date, datetime_time(0, 0, 0), tzinfo=SINGAPORE_TIMEZONE)
    end_local = datetime.combine(end_date, datetime_time(23, 59, 59), tzinfo=SINGAPORE_TIMEZONE)
    return {
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "start_dt": start_local.astimezone(timezone.utc),
        "end_dt": end_local.astimezone(timezone.utc),
        "timezone": "Asia/Singapore",
    }


def _safe_activity_label(value: Any, limit: int = 120) -> str:
    text = re.sub(r"(?<!\d)\+?\d[\d\s().-]{6,}\d(?!\d)", "[phone omitted]", str(value or ""))
    return _short_text(text, limit)


def _call_duration_ms(activity: dict[str, Any]) -> int:
    return _int_value(activity.get("properties", {}).get("hs_call_duration"))


def _is_completed_call(activity: dict[str, Any]) -> bool:
    status = str(activity.get("properties", {}).get("hs_call_status") or "").strip().upper()
    return status in {"COMPLETED", "DONE"}


def _is_connected_call(activity: dict[str, Any]) -> bool:
    return _is_completed_call(activity) and _call_duration_ms(activity) >= CONNECTED_CALL_MIN_DURATION_MS


def _is_completed_meeting(activity: dict[str, Any]) -> bool:
    outcome = str(activity.get("properties", {}).get("hs_meeting_outcome") or "").strip().upper()
    return outcome == "COMPLETED"


def _matching_warm_activity_label(activity: dict[str, Any]) -> str:
    props = activity.get("properties", {})
    text = " ".join(
        [
            str(props.get("hs_meeting_title") or ""),
            str(props.get("hs_activity_type") or ""),
        ]
    ).lower()
    for label in _warm_activity_labels():
        if label.lower() in text:
            return label
    return ""


def _safe_friday_activity_evidence(
    evidence_type: str,
    activity: dict[str, Any],
    activity_sources: dict[str, list[dict[str, str]]],
) -> dict[str, Any]:
    props = activity.get("properties", {})
    object_id = str(activity.get("id") or "")
    evidence: dict[str, Any] = {
        "object_type": evidence_type,
        "object_id": object_id,
        "timestamp": _activity_timestamp(activity),
        "owner_id": props.get("hubspot_owner_id") or "",
        "associated_via": activity_sources.get(object_id, []),
    }
    if evidence_type == "communication":
        evidence["channel"] = props.get("hs_communication_channel_type") or ""
    elif evidence_type == "task":
        evidence["status"] = props.get("hs_task_status") or ""
        evidence["subject"] = _safe_activity_label(props.get("hs_task_subject"))
    elif evidence_type == "call":
        evidence["title"] = _safe_activity_label(props.get("hs_call_title"))
        evidence["status"] = props.get("hs_call_status") or ""
        evidence["duration_seconds"] = round(_call_duration_ms(activity) / 1000)
        evidence["connected_call"] = _is_connected_call(activity)
    elif evidence_type == "meeting":
        warm_label = _matching_warm_activity_label(activity)
        evidence["title"] = _safe_activity_label(props.get("hs_meeting_title"))
        evidence["outcome"] = props.get("hs_meeting_outcome") or ""
        evidence["activity_type"] = _safe_activity_label(props.get("hs_activity_type"))
        evidence["warm_activity_label"] = warm_label
    return evidence


def _account_week_activity(
    company: dict[str, Any],
    contact_ids: list[str],
    deal_ids: list[str],
    since_dt: datetime,
    until_dt: datetime,
) -> dict[str, Any]:
    company_id = str(company.get("id") or "")
    counts = {
        "whatsapp_communications": 0,
        "notes": 0,
        "completed_tasks": 0,
        "open_tasks": 0,
        "completed_calls": 0,
        "connected_calls": 0,
        "completed_meetings": 0,
        "warm_activity_points": 0,
        "touches": 0,
    }
    evidence: list[dict[str, Any]] = []
    truncated = False
    weak_evidence = False
    activity_specs = [
        ("communications", "communication", COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("calls", "call", CALL_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]

    for hubspot_type, evidence_type, properties in activity_specs:
        association_data = _collect_activity_associations(company_id, contact_ids, deal_ids, hubspot_type)
        activity_ids = association_data["activity_ids"]
        read_ids = activity_ids[:FOLLOWUP_RETURN_LIMIT]
        raw_activities = _batch_read(hubspot_type, read_ids, properties)
        truncated = bool(truncated or association_data["truncated"] or len(activity_ids) > len(read_ids))

        for activity in raw_activities:
            if not _activity_timestamp(activity):
                weak_evidence = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue

            safe_evidence = _safe_friday_activity_evidence(evidence_type, activity, association_data["activity_sources"])
            if evidence_type == "communication":
                if not _is_whatsapp_communication(activity):
                    continue
                counts["whatsapp_communications"] += 1
                counts["touches"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "note":
                counts["notes"] += 1
                counts["touches"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "task":
                if _is_incomplete_task(activity):
                    counts["open_tasks"] += 1
                    evidence.append(safe_evidence)
                else:
                    counts["completed_tasks"] += 1
                    counts["touches"] += 1
                    evidence.append(safe_evidence)
            elif evidence_type == "call":
                if not _is_completed_call(activity):
                    continue
                counts["completed_calls"] += 1
                counts["touches"] += 1
                if _is_connected_call(activity):
                    counts["connected_calls"] += 1
                evidence.append(safe_evidence)
            elif evidence_type == "meeting":
                if not _is_completed_meeting(activity):
                    continue
                counts["completed_meetings"] += 1
                counts["touches"] += 1
                if safe_evidence.get("warm_activity_label"):
                    counts["warm_activity_points"] += 1
                evidence.append(safe_evidence)

    sorted_evidence = _sort_followup_evidence(evidence)
    return {
        "counts": counts,
        "latest_activity_at": sorted_evidence[0]["timestamp"] if sorted_evidence else "",
        "evidence": sorted_evidence[:10],
        "truncated": truncated,
        "weak_evidence": weak_evidence,
        "confidence": "needs-check" if truncated or weak_evidence else "verified",
    }


def _empty_week_activity() -> dict[str, Any]:
    return {
        "counts": {
            "whatsapp_communications": 0,
            "notes": 0,
            "completed_tasks": 0,
            "open_tasks": 0,
            "completed_calls": 0,
            "connected_calls": 0,
            "completed_meetings": 0,
            "warm_activity_points": 0,
            "touches": 0,
        },
        "latest_activity_at": "",
        "evidence": [],
        "truncated": False,
        "weak_evidence": False,
        "confidence": "verified",
    }


def _reverse_company_association_index(index: dict[str, list[str]]) -> dict[str, list[str]]:
    reverse: dict[str, list[str]] = {}
    for company_id, associated_ids in index.items():
        for associated_id in associated_ids:
            reverse.setdefault(str(associated_id), []).append(str(company_id))
    return reverse


def _add_indexed_activity_source(
    company_activity_sources: dict[str, dict[str, list[dict[str, str]]]],
    company_id: str,
    activity_id: str,
    source_type: str,
    source_id: str,
) -> None:
    if not company_id or not activity_id:
        return
    activity_sources = company_activity_sources.setdefault(str(company_id), {})
    sources = activity_sources.setdefault(str(activity_id), [])
    source = {"object_type": source_type, "object_id": str(source_id)}
    if source not in sources:
        sources.append(source)


def _count_indexed_activity(
    account_activity: dict[str, Any],
    evidence_type: str,
    activity: dict[str, Any],
    sources: list[dict[str, str]],
) -> None:
    counts = account_activity["counts"]
    activity_id = str(activity.get("id") or "")
    safe_evidence = _safe_friday_activity_evidence(evidence_type, activity, {activity_id: sources})
    if evidence_type == "communication":
        if not _is_whatsapp_communication(activity):
            return
        counts["whatsapp_communications"] += 1
        counts["touches"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "note":
        counts["notes"] += 1
        counts["touches"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "task":
        if _is_incomplete_task(activity):
            counts["open_tasks"] += 1
            account_activity["evidence"].append(safe_evidence)
        else:
            counts["completed_tasks"] += 1
            counts["touches"] += 1
            account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "call":
        if not _is_completed_call(activity):
            return
        counts["completed_calls"] += 1
        counts["touches"] += 1
        if _is_connected_call(activity):
            counts["connected_calls"] += 1
        account_activity["evidence"].append(safe_evidence)
    elif evidence_type == "meeting":
        if not _is_completed_meeting(activity):
            return
        counts["completed_meetings"] += 1
        counts["touches"] += 1
        if safe_evidence.get("warm_activity_label"):
            counts["warm_activity_points"] += 1
        account_activity["evidence"].append(safe_evidence)


def _week_activity_index_for_companies(
    companies: list[dict[str, Any]],
    contact_index: dict[str, list[str]],
    deal_index: dict[str, list[str]],
    since_dt: datetime,
    until_dt: datetime,
) -> dict[str, dict[str, Any]]:
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    if not company_ids:
        return {}

    activity_by_company = {company_id: _empty_week_activity() for company_id in company_ids}
    contact_to_companies = _reverse_company_association_index(contact_index)
    deal_to_companies = _reverse_company_association_index(deal_index)
    contact_ids = list(contact_to_companies.keys())
    deal_ids = list(deal_to_companies.keys())
    activity_specs = [
        ("communications", "communication", COMMUNICATION_PROPERTIES),
        ("notes", "note", NOTE_PROPERTIES),
        ("tasks", "task", TASK_PROPERTIES),
        ("calls", "call", CALL_PROPERTIES),
        ("meetings", "meeting", MEETING_PROPERTIES),
    ]

    for hubspot_type, evidence_type, properties in activity_specs:
        company_activity_sources: dict[str, dict[str, list[dict[str, str]]]] = {}

        for company_id, activity_ids in _batch_association_ids("companies", hubspot_type, company_ids).items():
            for activity_id in activity_ids:
                _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "company", company_id)

        for contact_id, activity_ids in _batch_association_ids("contacts", hubspot_type, contact_ids).items():
            for company_id in contact_to_companies.get(str(contact_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "contact", contact_id)

        for deal_id, activity_ids in _batch_association_ids("deals", hubspot_type, deal_ids).items():
            for company_id in deal_to_companies.get(str(deal_id), []):
                for activity_id in activity_ids:
                    _add_indexed_activity_source(company_activity_sources, company_id, activity_id, "deal", deal_id)

        activity_ids = sorted(
            {
                activity_id
                for activity_sources in company_activity_sources.values()
                for activity_id in activity_sources.keys()
            }
        )
        if not activity_ids:
            continue

        raw_activities = _batch_read(hubspot_type, activity_ids, properties)
        for activity in raw_activities:
            activity_id = str(activity.get("id") or "")
            if not activity_id:
                continue
            associated_companies = [
                company_id
                for company_id, activity_sources in company_activity_sources.items()
                if activity_id in activity_sources
            ]
            if not _activity_timestamp(activity):
                for company_id in associated_companies:
                    activity_by_company[company_id]["weak_evidence"] = True
                continue
            if not _is_activity_in_window(activity, since_dt, until_dt):
                continue
            for company_id in associated_companies:
                _count_indexed_activity(
                    activity_by_company[company_id],
                    evidence_type,
                    activity,
                    company_activity_sources[company_id][activity_id],
                )

    for account_activity in activity_by_company.values():
        sorted_evidence = _sort_followup_evidence(account_activity["evidence"])
        account_activity["latest_activity_at"] = sorted_evidence[0]["timestamp"] if sorted_evidence else ""
        account_activity["evidence"] = sorted_evidence[:10]
        account_activity["confidence"] = "needs-check" if account_activity.get("weak_evidence") else "verified"
    return activity_by_company


def _safe_contact_index(contact_index: dict[str, list[str]]) -> dict[str, list[dict[str, Any]]]:
    contact_ids = sorted({contact_id for contact_ids in contact_index.values() for contact_id in contact_ids})
    contacts_by_id = {
        str(contact.get("id") or ""): _safe_contact(contact)
        for contact in _batch_read("contacts", contact_ids, CONTACT_PROPERTIES)
        if contact.get("id")
    }
    return {
        str(company_id): [contacts_by_id[contact_id] for contact_id in contact_ids if contact_id in contacts_by_id]
        for company_id, contact_ids in contact_index.items()
    }


def _clean_lead_missing_fields(
    company: dict[str, Any],
    contact_count: int,
    contacts: list[dict[str, Any]] | None = None,
) -> list[str]:
    props = company.get("properties", {})
    missing: list[str] = []
    if not props.get("industry"):
        missing.append("industry")
    if not props.get("numberofemployees"):
        missing.append("headcount")
    if not props.get(CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("current tools")
    if not props.get(RENEWAL_SOURCE_OF_TRUTH_PROPERTY):
        missing.append("contract end date")
    if contact_count < 1:
        missing.append("associated contact")
    if _decision_maker_coverage(props, contacts, contact_count)["verified_decision_maker_count"] < 1:
        missing.append("decision maker")
    return missing


def _company_latest_safe_activity_at(company: dict[str, Any], account_activity: dict[str, Any]) -> str:
    props = company.get("properties", {})
    candidates = [
        account_activity.get("latest_activity_at") or "",
        props.get("notes_last_updated") or "",
        props.get("nurtureany_last_nurtured_at") or "",
        props.get("nurtureany_last_reviewed_at") or "",
    ]
    dated = [_datetime_value(str(value)) for value in candidates if value]
    dated = [value for value in dated if value]
    if not dated:
        return ""
    return max(dated).isoformat()


def _is_stale_account(company: dict[str, Any], account_activity: dict[str, Any], cutoff_dt: datetime) -> bool:
    latest = _datetime_value(_company_latest_safe_activity_at(company, account_activity))
    return not latest or latest < cutoff_dt


def _owner_lookup_by_id() -> dict[str, dict[str, Any]]:
    try:
        return {str(owner.get("id") or ""): owner for owner in _list_owners()}
    except HubSpotError:
        return {}


def _owner_display(owner_id: str, owner_lookup: dict[str, dict[str, Any]]) -> dict[str, str]:
    owner = owner_lookup.get(str(owner_id), {})
    return {
        "owner_id": str(owner_id),
        "owner_email": _normalize_email(str(owner.get("email") or "")),
        "owner_name": _owner_name(owner) if owner else "",
    }


def _detail_account_row(
    company: dict[str, Any],
    account_activity: dict[str, Any],
    missing_clean_lead_fields: list[str],
    open_followup_tasks: list[dict[str, Any]],
    decision_maker_coverage: dict[str, Any],
) -> dict[str, Any]:
    summary = _summarize_company(company)
    counts = account_activity.get("counts", {})
    return {
        "company_id": summary.get("company_id"),
        "name": summary.get("name"),
        "country": summary.get("country"),
        "owner_id": summary.get("owner_id"),
        "touch_count": counts.get("touches", 0),
        "latest_activity_at": _company_latest_safe_activity_at(company, account_activity),
        "connected_call_count": counts.get("connected_calls", 0),
        "warm_activity_points": counts.get("warm_activity_points", 0),
        "open_followup_task_count": len(open_followup_tasks),
        "missing_clean_lead_fields": missing_clean_lead_fields,
        "decision_maker_coverage": decision_maker_coverage,
        "decision_maker_coverage_status": decision_maker_coverage.get("status"),
        "decision_maker_count": decision_maker_coverage.get("verified_decision_maker_count", 0),
        "buying_role_contact_count": decision_maker_coverage.get("buying_role_contact_count", 0),
        "role_inferred_decision_maker_candidate_count": decision_maker_coverage.get(
            "role_inferred_decision_maker_candidate_count",
            0,
        ),
    }


def _main_priority_issue(row: dict[str, Any]) -> str:
    if row["worked_account_count"] < row["weekly_account_target"]:
        return "weak account coverage against 120/150 weekly baseline"
    if row["connected_call_count"] < CONNECTED_CALL_WEEKLY_TARGET:
        return "connected calls below 40-call guardrail"
    if row["single_touch_account_count"]:
        return "worked accounts lack double tap"
    if row["dirty_account_count"]:
        return "clean-lead fields incomplete"
    if row["warm_activity_points"] == 0:
        return "no warm activity proof logged"
    return "operating rhythm on track"


def _priority_owner_row(
    owner_id: str,
    companies: list[dict[str, Any]],
    owner_lookup: dict[str, dict[str, Any]],
    contact_index: dict[str, list[str]],
    contact_detail_index: dict[str, list[dict[str, Any]]],
    deal_index: dict[str, list[str]],
    task_index: dict[str, list[dict[str, Any]]],
    activity_index: dict[str, dict[str, Any]],
    since_dt: datetime,
    until_dt: datetime,
    stale_cutoff_dt: datetime,
) -> dict[str, Any]:
    worked_accounts = []
    double_tapped_accounts = []
    untouched_accounts = []
    stale_accounts = []
    dirty_accounts = []
    open_followup_account_rows = []
    missing_contact_account_count = 0
    missing_decision_maker_account_count = 0
    role_only_decision_maker_account_count = 0
    decision_maker_needs_check_account_count = 0
    connected_call_count = 0
    warm_activity_points = 0
    whatsapp_communications = 0
    activity_truncated = False
    weak_evidence = False

    for company in companies:
        company_id = str(company.get("id") or "")
        contact_ids = contact_index.get(company_id, [])
        deal_ids = deal_index.get(company_id, [])
        safe_contacts = contact_detail_index.get(company_id, [])
        account_activity = activity_index.get(company_id) or _account_week_activity(
            company,
            contact_ids,
            deal_ids,
            since_dt,
            until_dt,
        )
        counts = account_activity.get("counts", {})
        open_followup_tasks = task_index.get(company_id, [])
        decision_maker_coverage = _decision_maker_coverage(company.get("properties", {}), safe_contacts, len(contact_ids))
        missing_clean_lead_fields = _clean_lead_missing_fields(company, len(contact_ids), safe_contacts)
        detail = _detail_account_row(
            company,
            account_activity,
            missing_clean_lead_fields,
            open_followup_tasks,
            decision_maker_coverage,
        )

        if counts.get("touches", 0) > 0:
            worked_accounts.append(detail)
        else:
            untouched_accounts.append(detail)
        if counts.get("touches", 0) >= 2:
            double_tapped_accounts.append(detail)
        if _is_stale_account(company, account_activity, stale_cutoff_dt):
            stale_accounts.append(detail)
        if missing_clean_lead_fields:
            dirty_accounts.append(detail)
        if open_followup_tasks:
            open_followup_account_rows.append(detail)
        if "associated contact" in missing_clean_lead_fields:
            missing_contact_account_count += 1
        if "decision maker" in missing_clean_lead_fields:
            missing_decision_maker_account_count += 1
        if (
            decision_maker_coverage.get("verified_decision_maker_count", 0) < 1
            and decision_maker_coverage.get("role_inferred_decision_maker_candidate_count", 0) > 0
        ):
            role_only_decision_maker_account_count += 1
        if decision_maker_coverage.get("status") == "needs-check":
            decision_maker_needs_check_account_count += 1

        connected_call_count += counts.get("connected_calls", 0)
        warm_activity_points += counts.get("warm_activity_points", 0)
        whatsapp_communications += counts.get("whatsapp_communications", 0)
        activity_truncated = bool(activity_truncated or account_activity.get("truncated"))
        weak_evidence = bool(weak_evidence or account_activity.get("weak_evidence"))

    locked_pool_count = len(companies)
    weekly_target = min(PRIORITY_ACCOUNT_WEEKLY_WORKED_TARGET, locked_pool_count)
    worked_account_count = len(worked_accounts)
    owner_data = _owner_display(owner_id, owner_lookup)
    row: dict[str, Any] = {
        **owner_data,
        "locked_pool_count": locked_pool_count,
        "weekly_account_target": weekly_target,
        "worked_account_count": worked_account_count,
        "120_150_accounts_worked": f"{worked_account_count}/{locked_pool_count} worked; target {weekly_target}/{PRIORITY_ACCOUNT_LOCKED_POOL_BASELINE}",
        "coverage_hit_miss": "hit" if worked_account_count >= weekly_target else "miss",
        "double_tapped_account_count": len(double_tapped_accounts),
        "single_touch_account_count": max(worked_account_count - len(double_tapped_accounts), 0),
        "untouched_account_count": len(untouched_accounts),
        "stale_account_count": len(stale_accounts),
        "dirty_account_count": len(dirty_accounts),
        "missing_contact_account_count": missing_contact_account_count,
        "missing_decision_maker_account_count": missing_decision_maker_account_count,
        "role_only_decision_maker_account_count": role_only_decision_maker_account_count,
        "decision_maker_needs_check_account_count": decision_maker_needs_check_account_count,
        "open_followup_account_count": len(open_followup_account_rows),
        "connected_call_count": connected_call_count,
        "40_connected_calls": f"{connected_call_count}/{CONNECTED_CALL_WEEKLY_TARGET}",
        "connected_call_hit_miss": "hit" if connected_call_count >= CONNECTED_CALL_WEEKLY_TARGET else "miss",
        "warm_activity_points": warm_activity_points,
        "whatsapp_communications": whatsapp_communications,
        "friday_correction_needed": bool(
            worked_account_count < weekly_target
            or connected_call_count < CONNECTED_CALL_WEEKLY_TARGET
            or untouched_accounts
            or stale_accounts
            or dirty_accounts
        ),
        "untouched_accounts": untouched_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "stale_accounts": stale_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "dirty_accounts": dirty_accounts[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "open_followup_accounts": open_followup_account_rows[:FRIDAY_REVIEW_DETAIL_LIMIT],
        "evidence_completeness": "needs-check" if activity_truncated or weak_evidence else "complete",
        "activity_truncated": activity_truncated,
        "weak_activity_evidence": weak_evidence,
    }
    row["main_issue"] = _main_priority_issue(row)
    return row


def _priority_account_coverage(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
    manager_only: bool = False,
    include_internal: bool = False,
) -> dict[str, Any]:
    scope = _caller_scope(slack_user_email)
    if scope["kind"] == "blocked":
        return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
    if manager_only and scope["kind"] not in {"admin", "manager"}:
        return _blocked("Friday sales review is manager/admin only by default.", _scope_response(scope, list(scope.get("countries", ()))))

    selected = _safe_countries(countries, scope["countries"])
    if not selected:
        return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

    target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
    requested_limit = _bounded_int(limit, default=PRIORITY_ACCOUNT_RETURN_LIMIT, maximum=PRIORITY_ACCOUNT_RETURN_LIMIT)
    week = _week_window(week_start, week_end)
    data = _company_search(
        _target_filters(selected, target_owner_id),
        requested_limit,
        maximum=PRIORITY_ACCOUNT_RETURN_LIMIT,
        sorts=[{"propertyName": "hubspot_owner_id", "direction": "ASCENDING"}],
    )
    companies = data.get("results", [])
    company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
    contact_index = _batch_association_ids("companies", "contacts", company_ids)
    contact_detail_index = _safe_contact_index(contact_index)
    deal_index = _batch_association_ids("companies", "deals", company_ids)
    activity_index = _week_activity_index_for_companies(companies, contact_index, deal_index, week["start_dt"], week["end_dt"])

    by_owner: dict[str, list[dict[str, Any]]] = {}
    for company in companies:
        owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
        by_owner.setdefault(owner_id, []).append(company)

    owner_lookup = _owner_lookup_by_id()
    stale_cutoff_dt = week["end_dt"] - timedelta(days=STALE_ACCOUNT_DAYS)
    owner_rows = []
    task_context = _sales_followup_task_index_for_company_associations(
        companies,
        contact_index,
        deal_index,
        TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
    )
    task_index = task_context.get("tasks_by_company", {})
    task_truncated = bool(task_context.get("truncated"))
    task_indexes_by_owner: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for owner_id, owner_companies in by_owner.items():
        owner_task_index = {
            str(company.get("id") or ""): task_index.get(str(company.get("id") or ""), [])
            for company in owner_companies
            if company.get("id")
        }
        task_indexes_by_owner[owner_id] = owner_task_index
        owner_rows.append(
            _priority_owner_row(
                owner_id,
                owner_companies,
                owner_lookup,
                contact_index,
                contact_detail_index,
                deal_index,
                owner_task_index,
                activity_index,
                week["start_dt"],
                week["end_dt"],
                stale_cutoff_dt,
            )
        )

    owner_rows.sort(key=lambda row: (str(row.get("owner_email") or row.get("owner_id") or ""), str(row.get("owner_id") or "")))
    metadata = _search_metadata(data)
    activity_truncated = any(row.get("activity_truncated") for row in owner_rows)
    weak_evidence = any(row.get("weak_activity_evidence") for row in owner_rows)
    result_truncated = bool(metadata.get("truncated") or task_truncated or activity_truncated)
    scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
    scope_response.update(
        {
            "week_start": week["week_start"],
            "week_end": week["week_end"],
            "timezone": week["timezone"],
        }
    )
    response: dict[str, Any] = {
        "answer": {
            "owners": owner_rows,
            "summary": {
                "owner_count": len(owner_rows),
                "locked_pool_count": sum(row.get("locked_pool_count", 0) for row in owner_rows),
                "worked_account_count": sum(row.get("worked_account_count", 0) for row in owner_rows),
                "untouched_account_count": sum(row.get("untouched_account_count", 0) for row in owner_rows),
                "stale_account_count": sum(row.get("stale_account_count", 0) for row in owner_rows),
                "dirty_account_count": sum(row.get("dirty_account_count", 0) for row in owner_rows),
                "missing_contact_account_count": sum(row.get("missing_contact_account_count", 0) for row in owner_rows),
                "missing_decision_maker_account_count": sum(
                    row.get("missing_decision_maker_account_count", 0) for row in owner_rows
                ),
                "role_only_decision_maker_account_count": sum(
                    row.get("role_only_decision_maker_account_count", 0) for row in owner_rows
                ),
                "decision_maker_needs_check_account_count": sum(
                    row.get("decision_maker_needs_check_account_count", 0) for row in owner_rows
                ),
                "connected_call_count": sum(row.get("connected_call_count", 0) for row in owner_rows),
                "warm_activity_points": sum(row.get("warm_activity_points", 0) for row in owner_rows),
                "friday_correction_owner_count": len([row for row in owner_rows if row.get("friday_correction_needed")]),
            },
        },
        "source": "HubSpot target-account companies plus safe calls, meetings, communications, notes, tasks, and associations",
        "scope": scope_response,
        **metadata,
        "confidence": "needs-check" if result_truncated or weak_evidence else "verified",
        "caveat": _coverage_caveat(
            {**metadata, "truncated": result_truncated},
            "Read-only priority account coverage audit. Raw call bodies, meeting bodies, recordings, phone numbers, note bodies, task bodies, attachments, and exports are omitted.",
        ),
    }
    if include_internal:
        response["_internal"] = {
            "companies": companies,
            "company_contact_ids": contact_index,
            "company_deal_ids": deal_index,
            "task_indexes_by_owner": task_indexes_by_owner,
            "week": week,
        }
    return response


def _date_in_week(value: str, week: dict[str, Any]) -> bool:
    parsed = _datetime_value(value)
    return bool(parsed and week["start_dt"] <= parsed <= week["end_dt"])


def _deal_counts_for_friday(
    companies: list[dict[str, Any]],
    company_deal_ids: dict[str, list[str]],
    week: dict[str, Any],
    stage_config: dict[str, Any],
) -> dict[str, Any]:
    deal_ids: list[str] = []
    company_owner_by_deal: dict[str, str] = {}
    for company in companies:
        owner_id = str(company.get("properties", {}).get("hubspot_owner_id") or "")
        company_id = str(company.get("id") or "")
        for deal_id in company_deal_ids.get(company_id, []):
            if deal_id not in deal_ids:
                deal_ids.append(deal_id)
                company_owner_by_deal[deal_id] = owner_id

    if not stage_config.get("configured"):
        return {
            "configured": False,
            "by_owner": {},
            "totals": {"qos": None, "qo_met": None, "qo_met_pct": None, "deals_closed": None},
            "confidence": "needs-check",
            "caveat": "QO, QO Met, and closed-won stage IDs are not fully configured; hygiene and activity counts are still returned.",
        }

    raw_deals = _batch_read("deals", deal_ids, DEAL_PROPERTIES)
    by_owner: dict[str, dict[str, Any]] = {}
    totals = {"qos": 0, "qo_met": 0, "deals_closed": 0}
    weak_dates = False
    for deal in raw_deals:
        props = deal.get("properties", {})
        if stage_config["pipeline_ids"] and str(props.get("pipeline") or "") not in stage_config["pipeline_ids"]:
            continue
        deal_id = str(deal.get("id") or "")
        owner_id = str(props.get("hubspot_owner_id") or company_owner_by_deal.get(deal_id) or "")
        owner_counts = by_owner.setdefault(owner_id, {"qos": 0, "qo_met": 0, "deals_closed": 0})
        stage = str(props.get("dealstage") or "")
        createdate = str(props.get("createdate") or props.get("hs_lastmodifieddate") or "")
        closedate = str(props.get("closedate") or "")

        if stage in stage_config["qo_stage_ids"]:
            if _date_in_week(createdate, week):
                totals["qos"] += 1
                owner_counts["qos"] += 1
            elif not createdate:
                weak_dates = True
        if stage in stage_config["qo_met_stage_ids"]:
            if _date_in_week(createdate, week):
                totals["qo_met"] += 1
                owner_counts["qo_met"] += 1
            elif not createdate:
                weak_dates = True
        if stage in stage_config["closed_won_stage_ids"]:
            if _date_in_week(closedate, week):
                totals["deals_closed"] += 1
                owner_counts["deals_closed"] += 1
            elif not closedate:
                weak_dates = True

    totals["qo_met_pct"] = round((totals["qo_met"] / totals["qos"]) * 100, 1) if totals["qos"] else None
    for owner_counts in by_owner.values():
        owner_counts["qo_met_pct"] = round((owner_counts["qo_met"] / owner_counts["qos"]) * 100, 1) if owner_counts["qos"] else None
    return {
        "configured": True,
        "by_owner": by_owner,
        "totals": totals,
        "confidence": "needs-check" if weak_dates else "verified",
        "caveat": "Deal funnel counts use configured HubSpot pipeline/stage IDs and safe deal dates; no deal bodies or attachments are exported.",
    }


def _friday_hygiene_summary(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in owner_rows:
        rows.append(
            {
                "ae": row.get("owner_email") or row.get("owner_name") or row.get("owner_id"),
                "owner_id": row.get("owner_id"),
                "120_150_accounts_worked": row.get("120_150_accounts_worked"),
                "40_connected_calls": row.get("40_connected_calls"),
                "hit_miss": "hit"
                if row.get("coverage_hit_miss") == "hit" and row.get("connected_call_hit_miss") == "hit"
                else "miss",
                "friday_correction_needed": row.get("friday_correction_needed"),
                "main_issue": row.get("main_issue"),
                "locked_pool_count": row.get("locked_pool_count"),
                "worked_account_count": row.get("worked_account_count"),
                "double_tapped_account_count": row.get("double_tapped_account_count"),
                "untouched_account_count": row.get("untouched_account_count"),
                "stale_account_count": row.get("stale_account_count"),
                "dirty_account_count": row.get("dirty_account_count"),
                "missing_contact_account_count": row.get("missing_contact_account_count"),
                "missing_decision_maker_account_count": row.get("missing_decision_maker_account_count"),
                "role_only_decision_maker_account_count": row.get("role_only_decision_maker_account_count"),
                "decision_maker_needs_check_account_count": row.get("decision_maker_needs_check_account_count"),
                "warm_activity_points": row.get("warm_activity_points"),
            }
        )
    return rows


def _friday_funnel_snapshot(owner_rows: list[dict[str, Any]], deal_counts: dict[str, Any]) -> dict[str, Any]:
    by_ae = []
    for row in owner_rows:
        owner_id = str(row.get("owner_id") or "")
        owner_deals = deal_counts.get("by_owner", {}).get(owner_id, {})
        by_ae.append(
            {
                "ae": row.get("owner_email") or row.get("owner_name") or owner_id,
                "owner_id": owner_id,
                "accounts_worked": row.get("worked_account_count", 0),
                "connected_calls": row.get("connected_call_count", 0),
                "qos": owner_deals.get("qos") if deal_counts.get("configured") else None,
                "qo_met": owner_deals.get("qo_met") if deal_counts.get("configured") else None,
                "qo_met_pct": owner_deals.get("qo_met_pct") if deal_counts.get("configured") else None,
                "deals_closed": owner_deals.get("deals_closed") if deal_counts.get("configured") else None,
                "warm_activity_points": row.get("warm_activity_points", 0),
                "caveats": [
                    caveat
                    for caveat in [
                        "activity evidence truncated" if row.get("activity_truncated") else "",
                        "activity timestamp evidence incomplete" if row.get("weak_activity_evidence") else "",
                    ]
                    if caveat
                ],
            }
        )

    team_totals = {
        "accounts_worked": sum(row.get("worked_account_count", 0) for row in owner_rows),
        "connected_calls": sum(row.get("connected_call_count", 0) for row in owner_rows),
        "qos": deal_counts.get("totals", {}).get("qos"),
        "qo_met": deal_counts.get("totals", {}).get("qo_met"),
        "qo_met_pct": deal_counts.get("totals", {}).get("qo_met_pct"),
        "deals_closed": deal_counts.get("totals", {}).get("deals_closed"),
        "warm_activity_points": sum(row.get("warm_activity_points", 0) for row in owner_rows),
    }
    return {"team_totals": team_totals, "by_ae": by_ae, "caveats": [deal_counts.get("caveat")]}


def _coaching_observations(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observations = []
    for row in owner_rows:
        ae = row.get("owner_email") or row.get("owner_name") or row.get("owner_id")
        if row.get("worked_account_count", 0) < row.get("weekly_account_target", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Account coverage missed the 120/150 weekly rhythm.",
                    "evidence": row.get("120_150_accounts_worked"),
                }
            )
        if row.get("single_touch_account_count", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Double tap is incomplete; worked accounts have only one logged touch.",
                    "evidence": f"{row.get('single_touch_account_count')} single-touch account(s)",
                }
            )
        if row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
            observations.append(
                {
                    "ae": ae,
                    "observation": "Connected-call volume is below the 40-call weekly guardrail.",
                    "evidence": row.get("40_connected_calls"),
                }
            )
        if row.get("dirty_account_count", 0):
            observations.append(
                {
                    "ae": ae,
                    "observation": "Clean-lead coverage is weak for part of the locked pool.",
                    "evidence": (
                        f"{row.get('dirty_account_count')} dirty/unworkable account(s); "
                        f"{row.get('missing_contact_account_count', 0)} missing contact, "
                        f"{row.get('missing_decision_maker_account_count', 0)} missing decision maker"
                    ),
                }
            )
        if row.get("warm_activity_points", 0) == 0:
            observations.append(
                {
                    "ae": ae,
                    "observation": "No warm activity proof was found in completed meetings.",
                    "evidence": "0 warm activity points",
                }
            )
    return observations[:20]


def _next_week_actions(owner_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions = []
    for row in owner_rows:
        ae = row.get("owner_email") or row.get("owner_name") or row.get("owner_id")
        if row.get("untouched_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Start Monday by clearing untouched locked accounts until 120/150 coverage is back on pace.",
                    "accounts": row.get("untouched_accounts", [])[:10],
                }
            )
        if row.get("single_touch_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Double tap the single-touch accounts before Friday correction; use WhatsApp plus a call or meeting ask.",
                    "count": row.get("single_touch_account_count"),
                }
            )
        if row.get("connected_call_count", 0) < CONNECTED_CALL_WEEKLY_TARGET:
            actions.append(
                {
                    "ae": ae,
                    "action": "Plan call blocks to reach 40 connected calls, counting only completed HubSpot calls of at least 120 seconds.",
                    "current": row.get("connected_call_count"),
                    "target": CONNECTED_CALL_WEEKLY_TARGET,
                }
            )
        if row.get("dirty_account_count", 0):
            actions.append(
                {
                    "ae": ae,
                    "action": "Clean dirty accounts before pushing them through nurture: industry, headcount, current tools, contract end date, associated contact, and verified decision maker.",
                    "accounts": row.get("dirty_accounts", [])[:10],
                }
            )
        if row.get("warm_activity_points", 0) == 0:
            actions.append(
                {
                    "ae": ae,
                    "action": "Book and log one warm activity with a completed meeting title/type such as HHH, LL, coffee, lunch, dinner, cosy, ABM, event, appreciation afternoon, or sports.",
                }
            )
    return actions[:30]


def _support_needed(coverage: dict[str, Any], deal_counts: dict[str, Any]) -> list[str]:
    support = []
    if coverage.get("truncated"):
        support.append("Increase or narrow the scoped account limit before presenting exact team counts.")
    if coverage.get("confidence") == "needs-check":
        support.append("Review accounts with truncated or weak activity evidence before using the report in coaching.")
    if not deal_counts.get("configured"):
        support.append(
            "Configure HubSpot pipeline/stage IDs for QO, QO Met, and closed-won counts before treating funnel numbers as verified."
        )
    elif deal_counts.get("confidence") == "needs-check":
        support.append("Review deal date completeness for QO/QO Met/closed-won attribution.")
    return support


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


def _list_sales_followup_tasks_from_task_search(
    scope: dict[str, Any],
    selected: list[str],
    requested_limit: int,
    target_owner_id: str | None,
    target_owner_email: str,
    due_start: str = "",
    due_end: str = "",
) -> dict[str, Any]:
    search_limit = min(TASK_SEARCH_RESULT_LIMIT, max(requested_limit * 5, 20))
    task_data = _task_search(_task_search_filters(target_owner_id, due_start, due_end), search_limit)
    task_ids = [str(task.get("id") or "") for task in task_data.get("results", []) if task.get("id")]
    task_links = _task_company_links_for_tasks(task_ids)
    candidate_company_ids: list[str] = []
    association_truncated = False

    for links in task_links.values():
        association_truncated = association_truncated or bool(links.get("truncated"))
        for company_id in links.get("company_ids", []):
            if company_id not in candidate_company_ids:
                candidate_company_ids.append(company_id)

    companies = {
        str(company.get("id")): company
        for company in _batch_read("companies", candidate_company_ids, COMPANY_PROPERTIES)
        if company.get("id")
    }
    rows: list[dict[str, Any]] = []
    seen_task_ids: set[str] = set()

    for task in task_data.get("results", []):
        task_id = str(task.get("id") or "")
        if not task_id or task_id in seen_task_ids or not _is_incomplete_task(task):
            continue
        task_owner_id = str(task.get("properties", {}).get("hubspot_owner_id") or "")
        links = task_links.get(task_id, {})
        for company_id in links.get("company_ids", []):
            company = companies.get(str(company_id))
            if not company or not _has_company_access(company, scope):
                continue
            props = company.get("properties", {})
            company_owner_id = str(props.get("hubspot_owner_id") or "")
            if props.get("company_country") not in selected:
                continue
            if target_owner_id and company_owner_id != str(target_owner_id):
                continue
            if task_owner_id and company_owner_id != task_owner_id:
                continue

            summary = _summarize_company(company)
            task_summary = _safe_task_summary(
                task,
                {task_id: links.get("company_sources", {}).get(str(company_id), [])},
            )
            rows.append(
                {
                    "company_id": summary.get("company_id"),
                    "company_name": summary.get("name"),
                    "country": summary.get("country"),
                    **task_summary,
                }
            )
            seen_task_ids.add(task_id)
            break

    sorted_tasks = _sort_tasks_by_due_at(rows)
    returned_tasks = sorted_tasks[:requested_limit]
    metadata = _search_metadata(task_data)
    task_truncated = bool(metadata.get("truncated") or association_truncated or len(sorted_tasks) > requested_limit)
    scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
    if due_start:
        scope_response["due_start"] = due_start
    if due_end:
        scope_response["due_end"] = due_end
    return {
        "answer": returned_tasks,
        "source": "HubSpot task search plus scoped sales-owned task associations",
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


def _get_company(company_id: str) -> dict[str, Any]:
    props = ",".join(COMPANY_PROPERTIES)
    return _get(f"/crm/v3/objects/companies/{company_id}", {"properties": props})


def _has_company_access(company: dict[str, Any], scope: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    if str(props.get("hs_is_target_account") or "").lower() != "true":
        return False
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
    company_summary["calendar_audit_seed"] = _calendar_audit_seed(company_summary, contacts)
    return {
        "company": company_summary,
        "contacts": safe_contacts,
        "deals": [_safe_deal(deal) for deal in deals],
        "sales_followup_tasks": task_context["tasks"],
        "coverage": _coverage(props, safe_contacts),
    }


def _assert_company_access(company_id: str, scope: dict[str, Any]) -> dict[str, Any]:
    company = _get_company(company_id)
    if not _has_company_access(company, scope):
        raise ScopeError("Company is outside caller scope or is not a HubSpot target account.")
    return company


def _summarize_company_with_contacts(
    company: dict[str, Any],
    contacts: list[dict[str, Any]],
    contact_count: int | None = None,
) -> dict[str, Any]:
    summary = _summarize_company(company)
    props = company.get("properties", {})
    associated_contact_count = len(contacts) if contact_count is None else contact_count
    decision_coverage = _decision_maker_coverage(props, contacts, associated_contact_count)
    contact_detail_missing = _contact_detail_missing_fields(contacts)
    summary["contact_count"] = associated_contact_count
    summary["associated_contact_count"] = associated_contact_count
    summary["verified_decision_maker_count"] = decision_coverage["verified_decision_maker_count"]
    summary["decision_maker_count"] = decision_coverage["verified_decision_maker_count"]
    summary["role_inferred_decision_maker_count"] = decision_coverage["role_inferred_decision_maker_candidate_count"]
    summary["role_inferred_decision_maker_candidate_count"] = decision_coverage["role_inferred_decision_maker_candidate_count"]
    summary["decision_maker_coverage"] = decision_coverage
    summary["enrichment_status"] = _enrichment_status(props, associated_contact_count, contacts)
    summary["missing_fields"] = _missing_company_fields(props, associated_contact_count, contacts) + contact_detail_missing
    summary["calendar_scan_instruction"] = _calendar_scan_instruction(summary)
    return summary


def _safe_contact(contact: dict[str, Any]) -> dict[str, Any]:
    props = contact.get("properties", {})
    first = props.get("firstname") or ""
    last = props.get("lastname") or ""
    role = props.get("job_role") or props.get("jobtitle") or ""
    buying_role = props.get("hs_buying_role") or ""
    has_verified_decision_maker_role = _has_decision_maker_buying_role(buying_role)
    has_role_inferred_decision_maker = _role_is_decision_maker(role)
    return {
        "contact_id": contact.get("id"),
        "display_name": " ".join(part for part in [first, last[:1] + "." if last else ""] if part).strip(),
        "persona": role,
        "buying_role": buying_role,
        "is_verified_decision_maker": has_verified_decision_maker_role,
        "is_role_inferred_decision_maker": has_role_inferred_decision_maker,
        "is_decision_maker": has_verified_decision_maker_role or has_role_inferred_decision_maker,
        "decision_maker_confidence": "verified" if has_verified_decision_maker_role else "needs-check" if has_role_inferred_decision_maker else "",
        "last_verified_at": props.get("nurtureany_last_verified_at") or props.get("lastmodifieddate") or "",
        "channel_fit": props.get("nurtureany_channel_fit") or "",
        "contact_confidence": props.get("nurtureany_contact_confidence") or "",
    }


def _role_is_decision_maker(role: str) -> bool:
    text = role.lower()
    if "executive" in text:
        return False
    markers = ("founder", "owner", "director", "ceo", "chief", "boss")
    return any(marker in text for marker in markers)


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
    decision_coverage = _decision_maker_coverage(props, contacts, len(contacts))
    verified_decision_makers = [contact for contact in contacts if contact.get("is_verified_decision_maker")]
    role_inferred_decision_makers = [contact for contact in contacts if contact.get("is_role_inferred_decision_maker")]
    channel_known = [contact for contact in contacts if contact.get("channel_fit")]
    return {
        "contact_count": len(contacts),
        "associated_contact_count": len(contacts),
        "decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "verified_decision_maker_count": decision_coverage["verified_decision_maker_count"],
        "decision_maker_count_from_hubspot_property": decision_coverage["decision_maker_count_from_hubspot_property"],
        "decision_maker_count_from_contact_roles": len(verified_decision_makers),
        "decision_maker_count_from_contact_buying_role": len(verified_decision_makers),
        "buying_role_contact_count": decision_coverage["buying_role_contact_count"],
        "role_inferred_decision_maker_count": len(role_inferred_decision_makers),
        "role_inferred_decision_maker_candidate_count": decision_coverage["role_inferred_decision_maker_candidate_count"],
        "channel_fit_known_count": len(channel_known),
        "decision_maker_coverage": decision_coverage,
        "sources": _decision_maker_count_source(props),
        "summary": (
            "nurture-ready"
            if contacts and decision_coverage["verified_decision_maker_count"] and channel_known
            else "minimum coverage" if contacts and decision_coverage["verified_decision_maker_count"] else "needs enrichment"
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
            reasons.append(f"contract end in {days} days")
        elif 91 <= days <= 180:
            score += 20
            reasons.append(f"contract end in {days} days")
    else:
        score += 10
        reasons.append("missing contract end date")

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
    if any("contract end" in reason for reason in reasons):
        return "Renewal / contract-end alert"
    if "decision maker" in " ".join(summary.get("missing_fields", [])).lower():
        return "Missing direct contact"
    if summary.get("prospecting_account") == "true":
        return "Pre-demo target account"
    return "High-value dormant account"


def _pre_demo_stakeholder_text(contacts: list[dict[str, Any]]) -> str:
    if not contacts:
        return "meeting attendee needed"
    selected = next((contact for contact in contacts if contact.get("is_decision_maker")), contacts[0])
    display_name = selected.get("display_name") or "HubSpot contact"
    persona = selected.get("persona") or selected.get("buying_role") or "persona needed"
    return f"not confirmed; HubSpot contact: {display_name} ({persona})"


def _pre_demo_role_bucket(contacts: list[dict[str, Any]]) -> str:
    text = " ".join(str(contact.get("persona") or contact.get("buying_role") or "") for contact in contacts).lower()
    if any(marker in text for marker in ("founder", "owner", "ceo", "chief", "boss")):
        return "owner"
    if any(marker in text for marker in ("ops", "operation", "gm", "general manager", "coo")):
        return "ops"
    if any(marker in text for marker in ("hr", "people", "human resource", "talent")):
        return "hr"
    if any(marker in text for marker in ("finance", "payroll", "account")):
        return "finance"
    return "unknown"


def _pre_demo_industry_bucket(company: dict[str, Any]) -> str:
    industry = str(company.get("industry") or "").lower()
    if any(marker in industry for marker in ("f&b", "food", "restaurant", "cafe", "beverage")):
        return "fnb"
    if any(marker in industry for marker in ("hospitality", "hotel", "resort", "villa")):
        return "hospitality"
    if "retail" in industry:
        return "retail"
    return "general"


def _pre_demo_renewal_text(company: dict[str, Any]) -> str:
    contract = company.get("contract_end_date") or ""
    renewal = company.get("current_tool_renewal_date") or ""
    if contract:
        return str(contract)
    if renewal:
        return f"contract end date needed; current tool renewal context {renewal}"
    return "contract end date needed"


def _pre_demo_missing_evidence(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    missing = []
    field_checks = [
        ("number of employees", company.get("headcount")),
        ("industry", company.get("industry")),
        ("confirmed meeting attendees", contacts),
        ("current tools", company.get("current_tools")),
        ("contract end date", company.get("contract_end_date")),
    ]
    for label, value in field_checks:
        if not value:
            missing.append(label)
    for label in ["lead source", "meeting reason", "pricing", "3 case-study matches"]:
        if label not in missing:
            missing.append(label)
    return missing


def _pre_demo_known_signals(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    coverage = context.get("coverage", {})
    signals = []
    if company.get("account_status"):
        signals.append(f"account status: {company.get('account_status')} ({company.get('account_status_source')})")
    if company.get("owner_email") or company.get("owner_name"):
        signals.append(f"HubSpot owner: {company.get('owner_name') or company.get('owner_email')} ({company.get('owner_email') or company.get('owner_id')})")
    if company.get("industry"):
        signals.append(f"industry: {company.get('industry')}")
    if company.get("headcount"):
        signals.append(f"headcount: {company.get('headcount')}")
    if company.get("current_tools"):
        signals.append(f"current tools: {company.get('current_tools')}")
    if company.get("contract_end_date"):
        signals.append(f"contract end date: {_pre_demo_renewal_text(company)}")
    if coverage.get("decision_maker_count"):
        signals.append(
            "decision-maker coverage exists in HubSpot "
            f"(hs_num_decision_makers={coverage.get('decision_maker_count_from_hubspot_property')}, "
            f"role-inferred candidates={coverage.get('role_inferred_decision_maker_candidate_count')})"
        )
    if company.get("sales_followup_task_count"):
        signals.append(f"{company.get('sales_followup_task_count')} open sales-owned follow-up task(s)")
    if company.get("overdue_sales_followup_task_count"):
        signals.append(f"{company.get('overdue_sales_followup_task_count')} overdue sales-owned follow-up task(s)")
    return signals or ["HubSpot has limited commercial context; use IC-BANT before demo depth"]


def _pre_demo_hypothesized_interest(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    industry_bucket = _pre_demo_industry_bucket(company)
    role_bucket = _pre_demo_role_bucket(contacts)
    interests: list[str] = []
    renewal = _date_value(company.get("contract_end_date"))
    today = datetime.now(timezone.utc).date()
    if renewal:
        days = (renewal - today).days
        if 0 <= days <= 180:
            if company.get("account_status") == "customer":
                interests.append(f"customer contract end timing is active ({days} days out), so StaffAny renewal/retention risk is likely")
            else:
                interests.append(
                    f"contract timing is active ({days} days out), but account status is {company.get('account_status') or 'unknown'}; treat this as prospect/incumbent-tool timing until customer status is verified"
                )
    if company.get("decision_maker_count") or company.get("buying_role_contact_count"):
        interests.append("there is some decision-maker coverage, so use the call to confirm authority and decision process")
    else:
        interests.append("decision-maker coverage is weak, so the first job is to map authority before over-demoing")
    if industry_bucket in {"fnb", "hospitality", "retail"}:
        interests.append("shift-based workforce likely makes scheduling, attendance, timesheet, and payroll handoff commercially relevant")
    if role_bucket == "owner":
        interests.append("owner/founder persona likely cares about ROI, labour leakage, and operational control")
    elif role_bucket == "ops":
        interests.append("ops persona likely cares about roster changes, attendance visibility, and outlet execution")
    elif role_bucket == "hr":
        interests.append("HR persona likely cares about payroll accuracy, compliance, adoption, and support")
    elif role_bucket == "finance":
        interests.append("finance/payroll persona likely cares about clean timesheet-to-payroll controls and error reduction")
    if company.get("overdue_sales_followup_task_count"):
        interests.append("existing overdue sales follow-up means the account needs a crisp next step, not a generic nurture touch")
    return interests[:5]


def _pre_demo_alternatives(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    alternatives = [
        "current tool needed before naming exact competitor",
        "status quo/manual process if the pain is not quantified",
    ]
    if company.get("contract_end_date"):
        alternatives.append(
            "StaffAny renewal/no-change risk" if company.get("account_status") == "customer" else "incumbent-tool renewal/no-change risk"
        )
    alternatives.append("cheaper HRIS/payroll option if the conversation becomes price-led")
    return alternatives


def _pre_demo_show_to_win(context: dict[str, Any]) -> list[str]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    industry_bucket = _pre_demo_industry_bucket(company)
    role_bucket = _pre_demo_role_bucket(contacts)
    show = []
    if industry_bucket in {"fnb", "hospitality", "retail"}:
        show.extend(
            [
                "schedule to attendance to timesheet to payroll flow, because shift-based work creates leakage before payroll",
                "CICO controls and late/no-show visibility, because frontline execution needs proof instead of trust-only tracking",
            ]
        )
    else:
        show.append("simple end-to-end workforce workflow, because the confirmed pain is still incomplete")
    if role_bucket == "owner":
        show.append("labour cost visibility and ROI framing, because owner personas need the commercial reason to change")
    elif role_bucket == "ops":
        show.append("live roster changes and manager workflow, because ops needs day-to-day control")
    elif role_bucket == "hr":
        show.append("payroll accuracy, compliance, and support flow, because HR needs confidence after go-live")
    else:
        show.append("IC-BANT discovery first, because stakeholder persona is not confirmed")
    if company.get("contract_end_date"):
        if company.get("account_status") == "customer":
            show.append("StaffAny renewal timeline and retention path, because verified customer status makes renewal the right motion")
        else:
            show.append("incumbent-tool contract timeline and migration path, because prospect/unknown status means this is not a confirmed StaffAny renewal")
    return show[:5]


def _pre_demo_game_plan(context: dict[str, Any], plan: str) -> dict[str, Any]:
    company = context.get("company", {})
    show_to_win = _pre_demo_show_to_win(context)
    if plan == "A":
        return {
            "route": "Primary route: prove the most likely operational pain with a tailored StaffAny flow.",
            "package_or_pricing": "pricing needed",
            "talk_track": [
                show_to_win[0],
                "Tie each feature to a commercial outcome: less admin rework, fewer errors, cleaner labour control.",
                "Ask what would make them confident enough to move to the next step.",
            ],
            "commercial_next_step": "propose the package only after pain, authority, and timeline are confirmed",
        }
    fallback = "pilot/proof-of-value"
    if company.get("contract_end_date"):
        fallback = "customer renewal path" if company.get("account_status") == "customer" else "contract-timed pilot or phased migration"
    return {
        "route": f"Fallback route: {fallback} if price, adoption risk, or incumbent inertia dominates.",
        "package_or_pricing": "pricing needed",
        "talk_track": [
            "Use a lighter scope, pilot, or proof-of-value rather than forcing the full pitch.",
            "Do not offer buyback or renewal displacement until current tool, contract terms, and approval path are confirmed.",
            "Anchor on value-vs-price if they compare against a cheaper HRIS/payroll option.",
        ],
        "commercial_next_step": "agree the smallest proof that would de-risk the decision",
    }


def _pre_demo_ic_bant_prompts(context: dict[str, Any]) -> dict[str, list[str]]:
    company = context.get("company", {})
    interest = _pre_demo_hypothesized_interest(context)[0]
    timeline_prompt = (
        "Is this a StaffAny renewal timeline, an incumbent-tool contract end, or a fresh buying process?"
        if company.get("account_status") != "customer"
        else "Is there a renewal deadline, payroll cycle, or internal target pushing this timeline?"
    )
    return {
        "intro_connect": [
            f"I saw {company.get('name') or 'your team'} is in {company.get('industry') or 'this space'}; what made this worth exploring now?",
            "Before I show product, can I understand how your team runs scheduling, attendance, and payroll today?",
        ],
        "budget": [
            f"If we solve this properly - {interest} - would it be fair to pay a slight premium for the better outcome?",
            "What is the cost today when this process breaks or needs manual correction?",
        ],
        "authority": [
            "Who owns this problem day to day, and who signs off if the team likes the solution?",
            "Last time you bought or renewed a workforce tool, who needed to be in the room?",
        ],
        "need": [
            "What are the top three annoying parts of scheduling, attendance, timesheet, or payroll right now?",
            "Where do managers or HR still need to double-check manually?",
        ],
        "timeline": [
            timeline_prompt,
            "If this saves labour leakage or admin time, do you want to compound that from this month or wait until later?",
        ],
    }


def _build_pre_demo_game_plan_row(context: dict[str, Any]) -> dict[str, Any]:
    company = context.get("company", {})
    contacts = context.get("contacts", [])
    coverage = context.get("coverage", {})
    missing = _pre_demo_missing_evidence(context)
    return {
        "company_id": company.get("company_id"),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "company_name": company.get("name"),
        "static_information": {
            "number_of_employees": company.get("headcount") or "number of employees needed",
            "industry": company.get("industry") or "industry needed",
            "account_status": company.get("account_status") or "account status needed",
            "account_status_source": company.get("account_status_source") or "customer/prospect source needed",
            "hubspot_owner": company.get("owner_name") or company.get("owner_email") or company.get("owner_id") or "owner needed",
            "hubspot_owner_email": company.get("owner_email") or "owner email needed",
            "how_did_they_hear_about_us": "lead source needed",
            "why_do_they_want_to_meet_with_us": "meeting reason needed",
            "who_will_i_be_meeting_with": _pre_demo_stakeholder_text(contacts),
            "current_tools": company.get("current_tools") or "current tool needed",
            "contract_end_date": _pre_demo_renewal_text(company),
        },
        "research_stalking_signal": {
            "known_hubspot_signals": _pre_demo_known_signals(context),
            "contact_coverage_source": coverage.get("sources") or _decision_maker_count_source({}),
            "calendar_scan_instruction": company.get("calendar_scan_instruction") or _calendar_scan_instruction(company),
            "manual_checks_needed": [
                "LinkedIn company/person profile manual check",
                "Instagram/Facebook/TikTok manual check where relevant",
                "news/search check for openings, awards, hiring, closures, or expansion",
            ],
            "rule": "Social/gated sources are manual-check only unless the user provides snippets.",
        },
        "hypothesized_interest_and_why": _pre_demo_hypothesized_interest(context),
        "alternatives_they_may_consider": _pre_demo_alternatives(context),
        "what_to_show_to_win": _pre_demo_show_to_win(context),
        "relevant_name_drops": [
            "case-study match needed",
            "case-study match needed",
            "case-study match needed",
        ],
        "game_plan_a": _pre_demo_game_plan(context, "A"),
        "game_plan_b": _pre_demo_game_plan(context, "B"),
        "ic_bant_prompts": _pre_demo_ic_bant_prompts(context),
        "missing_evidence": missing,
        "confidence": "needs-check" if missing else "verified",
    }


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
    if scope.get("hubspot_owner_email"):
        response["hubspot_owner_email"] = scope["hubspot_owner_email"]
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


def _dedup_append(values: list[str], value: Any, limit: int = 80) -> None:
    text = _short_text(str(value or ""), limit)
    if text and text not in values:
        values.append(text)


def _country_hint(value: str) -> str:
    normalized = (value or "").strip().lower()
    for country in SUPPORTED_COUNTRIES:
        if normalized == country.lower():
            return country
    text = f" {normalized} "
    aliases = {
        " sg ": "Singapore",
        " singapore ": "Singapore",
        " my ": "Malaysia",
        " malaysia ": "Malaysia",
        " id ": "Indonesia",
        " indonesia ": "Indonesia",
        " jakarta ": "Indonesia",
        " bali ": "Indonesia",
        " kuala lumpur ": "Malaysia",
    }
    for marker, country in aliases.items():
        if marker in text:
            return country
    return ""


def _as_hint_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _add_structured_photo_hints(hints: dict[str, list[str]], item: Any) -> None:
    if isinstance(item, dict):
        _dedup_append(hints["contact_names"], item.get("name") or item.get("person") or item.get("contact_name"))
        _dedup_append(hints["company_names"], item.get("company") or item.get("company_name") or item.get("account"))
        _dedup_append(hints["roles"], item.get("title") or item.get("jobtitle") or item.get("role"))
        _dedup_append(hints["event_names"], item.get("event") or item.get("event_name"))
        country = _country_hint(str(item.get("country") or item.get("location") or ""))
        if country:
            _dedup_append(hints["countries"], country)
        return
    _dedup_append(hints["contact_names"], item)


def _photo_matching_hints(
    context_text: str,
    vision_clues: dict[str, Any] | None,
    explicit_contact_name: str,
    explicit_company_name: str,
    event_name: str,
    country: str,
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    hints: dict[str, list[str]] = {
        "contact_names": [],
        "company_names": [],
        "event_names": [],
        "roles": [],
        "countries": [],
        "text_evidence": [],
    }
    _dedup_append(hints["contact_names"], explicit_contact_name)
    _dedup_append(hints["company_names"], explicit_company_name)
    _dedup_append(hints["event_names"], event_name)
    selected_country = _country_hint(country)
    if selected_country:
        _dedup_append(hints["countries"], selected_country)
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    if event_context.get("event_name"):
        _dedup_append(hints["event_names"], event_context.get("event_name"))
    if event_context.get("country"):
        _dedup_append(hints["countries"], event_context.get("country"))
    selected_event = event_context.get("selected_event") if isinstance(event_context.get("selected_event"), dict) else {}
    for key in ("tags", "location_tags", "event_type_tags"):
        for item in _as_hint_items(selected_event.get(key)):
            _dedup_append(hints["text_evidence"], item, 120)

    context = _short_text(context_text or "", 1000)
    if context:
        _dedup_append(hints["text_evidence"], context, 500)
        country_from_context = _country_hint(context)
        if country_from_context:
            _dedup_append(hints["countries"], country_from_context)
        person_company = re.search(
            r"(?:this is|meet|met|with)\s+([A-Za-z][A-Za-z'.-]*(?:\s+[A-Za-z][A-Za-z'.-]*){0,3})\s+(?:from|at)\s+([A-Za-z0-9][A-Za-z0-9&'. -]{1,70})",
            context,
            flags=re.IGNORECASE,
        )
        if person_company:
            _dedup_append(hints["contact_names"], person_company.group(1).strip())
            _dedup_append(hints["company_names"], person_company.group(2).strip(" .,:;"))

    clues = vision_clues if isinstance(vision_clues, dict) else {}
    for key in ("people", "persons", "faces", "badges"):
        for item in _as_hint_items(clues.get(key)):
            _add_structured_photo_hints(hints, item)
    for key in ("names", "person_names", "contact_names", "badge_names"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["contact_names"], item)
    for key in ("companies", "company_names", "accounts", "brands", "signage"):
        for item in _as_hint_items(clues.get(key)):
            if isinstance(item, dict):
                _add_structured_photo_hints(hints, item)
            else:
                _dedup_append(hints["company_names"], item)
    for key in ("roles", "titles", "job_titles"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["roles"], item)
    for key in ("event", "event_name", "events"):
        for item in _as_hint_items(clues.get(key)):
            _dedup_append(hints["event_names"], item)
    for key in ("country", "countries", "location", "locations"):
        for item in _as_hint_items(clues.get(key)):
            selected = _country_hint(str(item))
            if selected:
                _dedup_append(hints["countries"], selected)
    ocr_text = _short_text(str(clues.get("ocr_text") or clues.get("text") or ""), 1000)
    if ocr_text:
        _dedup_append(hints["text_evidence"], ocr_text, 500)
        selected = _country_hint(ocr_text)
        if selected:
            _dedup_append(hints["countries"], selected)

    return {key: value for key, value in hints.items() if value}


def _photo_source_type(value: str) -> str:
    source = (value or "").strip().lower()
    return source if source in PHOTO_SOURCE_TYPES else ""


def _metadata_value(metadata: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = metadata.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _parse_drive_photo_name(name: str) -> dict[str, str]:
    match = re.match(
        r"^(?P<source_timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)-(?P<slack_user_id>[UW][A-Z0-9]+)-(?P<original_filename>.+)$",
        name or "",
    )
    if not match:
        return {"source_timestamp": "", "slack_user_id": "", "original_filename": name or ""}
    return match.groupdict()


def _is_photo_file(metadata: dict[str, Any]) -> bool:
    mime_type = _metadata_value(metadata, "mimeType", "mime_type").lower()
    name = _metadata_value(metadata, "name", "filename", "title").lower()
    return mime_type.startswith("image/") or name.endswith(PHOTO_IMAGE_EXTENSIONS)


def _photo_source_pointer(photo_source: str, metadata: dict[str, Any]) -> dict[str, Any]:
    source = _photo_source_type(photo_source)
    if source == "drive":
        name = _metadata_value(metadata, "name", "filename", "title")
        parsed = _parse_drive_photo_name(name)
        return {
            "source_type": "drive",
            "drive_folder_id": _metadata_value(metadata, "folder_id", "folderId") or DRIVE_ALL_RANDOM_FOLDER_ID,
            "drive_file_id": _metadata_value(metadata, "id", "file_id", "fileId"),
            "drive_link": _metadata_value(metadata, "webViewLink", "web_view_link", "link"),
            "filename": name,
            "mime_type": _metadata_value(metadata, "mimeType", "mime_type"),
            "md5_checksum": _metadata_value(metadata, "md5Checksum", "md5_checksum"),
            "created_time": _metadata_value(metadata, "createdTime", "created_time"),
            "modified_time": _metadata_value(metadata, "modifiedTime", "modified_time"),
            "slack_uploader_name": _metadata_value(metadata, "slack_uploader_name", "uploader_name", "slackUploaderName"),
            **parsed,
        }
    if source == "slack":
        return {
            "source_type": "slack",
            "channel_id": _metadata_value(metadata, "channel_id", "channel", "channelId"),
            "message_ts": _metadata_value(metadata, "message_ts", "ts", "timestamp"),
            "file_id": _metadata_value(metadata, "file_id", "fileId", "id"),
            "permalink": _metadata_value(metadata, "permalink", "url_private", "url"),
            "filename": _metadata_value(metadata, "name", "filename", "title"),
            "uploader_user_id": _metadata_value(metadata, "user", "user_id", "uploader_user_id"),
            "slack_uploader_name": _metadata_value(metadata, "slack_uploader_name", "uploader_name", "slackUploaderName"),
            "mime_type": _metadata_value(metadata, "mimetype", "mimeType", "mime_type"),
            "created_time": _metadata_value(metadata, "created", "created_time", "timestamp"),
        }
    return {"source_type": source or "unknown"}


def _photo_key(source_pointer: dict[str, Any]) -> str:
    source = source_pointer.get("source_type")
    if source == "drive" and source_pointer.get("drive_file_id"):
        return f"drive:{source_pointer['drive_file_id']}"
    if source == "slack":
        parts = [source_pointer.get("channel_id"), source_pointer.get("message_ts"), source_pointer.get("file_id")]
        if all(parts):
            return "slack:" + ":".join(str(part) for part in parts)
    checksum = source_pointer.get("md5_checksum")
    if checksum:
        return f"hash:{checksum}"
    payload = json.dumps(source_pointer, sort_keys=True)
    return "photo:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _photo_custom_object_plan(
    photo_key: str,
    source_pointer: dict[str, Any],
    event_name: str = "",
    context_text: str = "",
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    selected_event = event_context.get("selected_event") if isinstance(event_context.get("selected_event"), dict) else {}
    event_label = _short_text(event_name or event_context.get("event_name") or "unclassified event photo", 120)
    return {
        "objects": PHOTO_CUSTOM_OBJECT_TYPES,
        "nurture_event": {
            "event_name": event_label,
            "source_context": _short_text(context_text or "", 240),
            "luma_event_id": selected_event.get("event_id") or "",
            "luma_event_url": selected_event.get("url") or "",
            "event_date_match_status": event_context.get("auto_event_tag_status") or "not_checked",
            "event_date_match_source": event_context.get("source") or "",
        },
        "nurture_event_photo": {
            "photo_key": photo_key,
            "source_pointer": source_pointer,
            "raw_image_copy": False,
        },
        "nurture_person_appearance": "created only after a human confirms the HubSpot contact/company match",
    }


def _photo_label(source_pointer: dict[str, Any]) -> str:
    return _short_text(
        str(
            source_pointer.get("original_filename")
            or source_pointer.get("filename")
            or source_pointer.get("drive_file_id")
            or source_pointer.get("file_id")
            or "this photo"
        ),
        120,
    )


def _photo_uploader_identity(source_pointer: dict[str, Any]) -> tuple[str, str]:
    user_id = str(source_pointer.get("slack_user_id") or source_pointer.get("uploader_user_id") or "").strip()
    name = str(source_pointer.get("slack_uploader_name") or source_pointer.get("uploader_name") or "").strip()
    return user_id, name


def _photo_confirmation_request(
    source_pointer: dict[str, Any],
    missing_clue_prompt: str = "",
    has_candidates: bool = False,
    luma_event_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    user_id, uploader_name = _photo_uploader_identity(source_pointer)
    label = _photo_label(source_pointer)
    recipient = f"<@{user_id}>" if user_id else (uploader_name or "the uploader")
    event_context = luma_event_context if isinstance(luma_event_context, dict) else {}
    event_suffix = f" for {event_context.get('event_name')}" if event_context.get("event_name") else ""
    if has_candidates:
        prompt = (
            f"{recipient} can you confirm the HubSpot contact/company for {label}{event_suffix}? "
            "Reply `confirm <contact> from <company>` or correct it."
        )
    else:
        clue = (missing_clue_prompt or "contact + company").strip()
        prompt = (
            f"{recipient} who is in {label}{event_suffix}? "
            f"Reply with {clue}, e.g. `Jane from Shake Shack`."
        )
    return {
        "required": True,
        "confirmation_owner": "slack_uploader" if user_id or uploader_name else "unknown_uploader",
        "delivery": "dm_or_thread_mention_uploader",
        "slack_user_id": user_id,
        "slack_uploader_name": uploader_name,
        "photo_label": label,
        "missing_clue_prompt": missing_clue_prompt,
        "luma_event_context": event_context,
        "prompt": prompt,
        "writes_blocked_until_confirmation": True,
    }


def _photo_confirmation_batches(photos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    batches: dict[str, dict[str, Any]] = {}
    for photo in photos:
        request = photo.get("confirmation_request") if isinstance(photo.get("confirmation_request"), dict) else {}
        user_id = str(request.get("slack_user_id") or "").strip()
        uploader_name = str(request.get("slack_uploader_name") or "").strip()
        key = user_id or uploader_name or "unknown_uploader"
        batch = batches.setdefault(
            key,
            {
                "confirmation_owner": request.get("confirmation_owner") or "unknown_uploader",
                "delivery": "dm_or_thread_mention_uploader",
                "slack_user_id": user_id,
                "slack_uploader_name": uploader_name,
                "photos": [],
                "writes_blocked_until_confirmation": True,
            },
        )
        batch["photos"].append(
            {
                "photo_key": photo.get("photo_key") or "",
                "photo_label": request.get("photo_label") or _photo_label(photo.get("source_pointer", {})),
                "source_timestamp": photo.get("source_timestamp") or "",
                "event_name": request.get("luma_event_context", {}).get("event_name")
                if isinstance(request.get("luma_event_context"), dict)
                else "",
            }
        )

    for batch in batches.values():
        recipient = f"<@{batch['slack_user_id']}>" if batch.get("slack_user_id") else (batch.get("slack_uploader_name") or "the uploader")
        count = len(batch["photos"])
        batch["prompt"] = (
            f"{recipient} can help identify these {count} photo(s)? "
            "Reply per filename with contact + company, e.g. `IMG_6194.jpg - Jane from Shake Shack`."
        )
    return list(batches.values())


def _luma_event_timezone(event: dict[str, Any]) -> timezone:
    text = str(event.get("timezone") or " ".join(str(tag) for tag in event.get("tags", []) if tag) or "").lower()
    if "jakarta" in text or "jkt" in text:
        return timezone(timedelta(hours=7))
    if "singapore" in text or "kuala_lumpur" in text or "kuala lumpur" in text or "bali" in text:
        return SINGAPORE_TIMEZONE
    return SINGAPORE_TIMEZONE


def _luma_event_country(event: dict[str, Any]) -> str:
    for country in event.get("country_tags", []) if isinstance(event.get("country_tags"), list) else []:
        selected = _country_hint(str(country))
        if selected:
            return selected
    for location in event.get("location_tags", []) if isinstance(event.get("location_tags"), list) else []:
        mapped = LOCATION_COUNTRY_MAP.get(str(location))
        if mapped:
            return mapped
    text_parts = [str(event.get("name") or ""), str(event.get("timezone") or "")]
    for key in ("tags", "event_type_tags"):
        if isinstance(event.get(key), list):
            text_parts.extend(str(item) for item in event[key])
    return _country_hint(" ".join(text_parts))


def _photo_source_datetime(source_pointer: dict[str, Any]) -> datetime | None:
    for key in ("source_timestamp", "created_time", "modified_time"):
        parsed = _datetime_value(str(source_pointer.get(key) or ""))
        if parsed:
            return parsed
    return None


def _event_date_delta_days(photo_dt: datetime, event: dict[str, Any]) -> int | None:
    start_dt = _datetime_value(str(event.get("start_at") or ""))
    if not start_dt:
        return None
    end_dt = _datetime_value(str(event.get("end_at") or "")) or start_dt
    event_timezone = _luma_event_timezone(event)
    photo_date = photo_dt.astimezone(event_timezone).date()
    start_date = start_dt.astimezone(event_timezone).date()
    end_date = end_dt.astimezone(event_timezone).date()
    if start_date <= photo_date <= end_date:
        return 0
    return min(abs((photo_date - start_date).days), abs((photo_date - end_date).days))


def _photo_luma_event_candidates(source_pointer: dict[str, Any], luma_events: Any, limit: int = PHOTO_LUMA_EVENT_CANDIDATE_LIMIT) -> list[dict[str, Any]]:
    if not isinstance(luma_events, list):
        return []
    photo_dt = _photo_source_datetime(source_pointer)
    if not photo_dt:
        return []

    candidates: list[dict[str, Any]] = []
    for event in luma_events:
        if not isinstance(event, dict):
            continue
        delta_days = _event_date_delta_days(photo_dt, event)
        if delta_days is None or delta_days > 1:
            continue
        score = 92 if delta_days == 0 else 70
        evidence = ["photo local date matches Luma event date" if delta_days == 0 else "photo local date is within one day of Luma event"]
        selected = {
            "event_id": str(event.get("event_id") or event.get("id") or "").strip(),
            "name": _short_text(str(event.get("name") or event.get("title") or ""), 160),
            "start_at": str(event.get("start_at") or ""),
            "end_at": str(event.get("end_at") or ""),
            "timezone": str(event.get("timezone") or ""),
            "url": str(event.get("url") or ""),
            "tags": event.get("tags") if isinstance(event.get("tags"), list) else [],
            "location_tags": event.get("location_tags") if isinstance(event.get("location_tags"), list) else [],
            "country_tags": event.get("country_tags") if isinstance(event.get("country_tags"), list) else [],
            "event_type_tags": event.get("event_type_tags") if isinstance(event.get("event_type_tags"), list) else [],
            "country": _luma_event_country(event),
            "confidence_score": score,
            "confidence_band": _confidence_band(score),
            "date_delta_days": delta_days,
            "evidence": evidence,
            "source": "luma_event_date",
        }
        if selected["name"]:
            candidates.append(selected)

    return sorted(candidates, key=lambda item: (item["confidence_score"], item.get("start_at", "")), reverse=True)[:limit]


def _photo_luma_event_context(source_pointer: dict[str, Any], luma_events: Any) -> dict[str, Any]:
    candidates = _photo_luma_event_candidates(source_pointer, luma_events)
    if not candidates:
        return {
            "source": "luma_event_date",
            "auto_event_tag_status": "not_found",
            "candidates": [],
        }
    top = candidates[0]
    close = [candidate for candidate in candidates if top["confidence_score"] - candidate["confidence_score"] <= 5]
    status = "verified" if top["confidence_score"] >= 90 and len(close) == 1 else "needs-check"
    return {
        "source": "luma_event_date",
        "auto_event_tag_status": status,
        "event_name": top.get("name") or "",
        "country": top.get("country") or "",
        "selected_event": top,
        "candidates": candidates,
        "requires_person_confirmation": True,
        "caveat": "Luma date match can tag the event context only; HubSpot contact association still requires uploader confirmation.",
    }


def _photo_scope_countries(scope: dict[str, Any], hints: dict[str, Any]) -> list[str]:
    hinted = [_country_hint(country) for country in hints.get("countries", [])]
    hinted = [country for country in hinted if country]
    selected = _safe_countries(hinted, scope.get("countries", ())) if hinted else list(scope.get("countries", ()))
    return selected


def _company_search_by_text(query: str, scope: dict[str, Any], countries: list[str], limit: int) -> dict[str, Any]:
    tokens = [token for token in _normalize_name(query).split() if len(token) > 1]
    filters = _target_filters(countries, scope.get("owner_id") if scope.get("kind") == "ae" else None)
    if tokens:
        filters.append({"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": tokens[0]})
    return _company_search(filters, limit)


def _contact_search_by_text(query: str, limit: int) -> dict[str, Any]:
    tokens = [token for token in _normalize_name(query).split() if len(token) > 1]
    if not tokens:
        return {"results": [], "total": 0, "requested_limit": limit, "returned_count": 0, "has_more": False, "truncated": False}
    filter_groups = []
    if len(tokens) >= 2:
        filter_groups.append(
            {
                "filters": [
                    {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": tokens[0]},
                    {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": tokens[-1]},
                ]
            }
        )
        filter_groups.append(
            {
                "filters": [
                    {"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": tokens[-1]},
                    {"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": tokens[0]},
                ]
            }
        )
    for token in tokens[:3]:
        filter_groups.append({"filters": [{"propertyName": "firstname", "operator": "CONTAINS_TOKEN", "value": token}]})
        filter_groups.append({"filters": [{"propertyName": "lastname", "operator": "CONTAINS_TOKEN", "value": token}]})
    requested_limit = _bounded_int(limit, default=PHOTO_MATCH_LIMIT, maximum=50)
    body = {
        "filterGroups": filter_groups[:8],
        "properties": CONTACT_PROPERTIES,
        "limit": requested_limit,
    }
    data = _post("/crm/v3/objects/contacts/search", body)
    return {
        "results": data.get("results", []),
        "total": data.get("total"),
        "requested_limit": requested_limit,
        "returned_count": len(data.get("results", [])),
        "has_more": bool(data.get("paging", {}).get("next", {}).get("after")),
        "truncated": bool(data.get("paging", {}).get("next", {}).get("after")),
    }


def _photo_company_candidates(scope: dict[str, Any], hints: dict[str, Any], limit: int) -> list[dict[str, Any]]:
    countries = _photo_scope_countries(scope, hints)
    if not countries:
        return []
    by_id: dict[str, dict[str, Any]] = {}
    queries = hints.get("company_names", [])[:5]
    for query in queries:
        data = _company_search_by_text(query, scope, countries, limit)
        for company in data.get("results", []):
            if not _has_company_access(company, scope):
                continue
            summary = _summarize_company(company)
            company_id = str(summary.get("company_id") or "")
            if not company_id:
                continue
            score = 55
            normalized_query = _normalize_name(query)
            normalized_name = _normalize_name(summary.get("name", ""))
            evidence = ["HubSpot scoped target account"]
            if normalized_query and normalized_query == normalized_name:
                score += 25
                evidence.append("company name exact match")
            elif normalized_query and normalized_query in normalized_name:
                score += 15
                evidence.append("company name contains provided hint")
            if summary.get("country") in hints.get("countries", []):
                score += 5
                evidence.append("country hint matches")
            existing = by_id.get(company_id)
            candidate = {
                "company_id": company_id,
                "name": summary.get("name"),
                "country": summary.get("country"),
                "owner_id": summary.get("owner_id"),
                "confidence_score": min(score, 100),
                "evidence": evidence,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
            }
            if not existing or candidate["confidence_score"] > existing["confidence_score"]:
                by_id[company_id] = candidate
    return sorted(by_id.values(), key=lambda item: item["confidence_score"], reverse=True)[:limit]


def _scoped_contact_companies(contact_id: str, scope: dict[str, Any]) -> list[dict[str, Any]]:
    company_ids = _association_ids("contacts", contact_id, "companies", 10)
    companies = _batch_read("companies", company_ids, COMPANY_PROPERTIES)
    summaries = []
    for company in companies:
        if _has_company_access(company, scope):
            summaries.append(_summarize_company(company))
    return summaries


def _photo_contact_score(
    contact: dict[str, Any],
    scoped_companies: list[dict[str, Any]],
    hints: dict[str, Any],
    company_candidates: list[dict[str, Any]],
) -> tuple[int, list[str]]:
    props = contact.get("properties", {})
    full_name = _contact_full_name(contact)
    normalized_full_name = _normalize_name(full_name)
    score = 20
    evidence = ["HubSpot contact associated to scoped target account"]
    for name in hints.get("contact_names", []):
        normalized_hint = _normalize_name(name)
        if normalized_hint and normalized_hint == normalized_full_name:
            score += 45
            evidence.append("contact name exact match")
            break
        if normalized_hint and normalized_hint in normalized_full_name:
            score += 30
            evidence.append("contact name partial match")
            break
    candidate_company_ids = {str(company.get("company_id") or "") for company in company_candidates}
    scoped_company_ids = {str(company.get("company_id") or "") for company in scoped_companies}
    if candidate_company_ids and scoped_company_ids & candidate_company_ids:
        score += 30
        evidence.append("associated company matches company hint")
    role_text = _normalize_name(" ".join([props.get("jobtitle") or "", props.get("job_role") or "", props.get("hs_buying_role") or ""]))
    for role in hints.get("roles", []):
        normalized_role = _normalize_name(role)
        if normalized_role and normalized_role in role_text:
            score += 10
            evidence.append("role/title clue matches")
            break
    hinted_countries = set(hints.get("countries", []))
    if hinted_countries and any(company.get("country") in hinted_countries for company in scoped_companies):
        score += 5
        evidence.append("associated company country matches")
    return min(score, 100), evidence


def _confidence_band(score: int) -> str:
    if score >= 80:
        return "high"
    if score >= 55:
        return "medium"
    return "low"


def _photo_contact_candidates(
    scope: dict[str, Any],
    hints: dict[str, Any],
    company_candidates: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for name in hints.get("contact_names", [])[:5]:
        data = _contact_search_by_text(name, limit * 6)
        for contact in data.get("results", []):
            contact_id = str(contact.get("id") or "")
            if not contact_id:
                continue
            scoped_companies = _scoped_contact_companies(contact_id, scope)
            if not scoped_companies:
                continue
            score, evidence = _photo_contact_score(contact, scoped_companies, hints, company_candidates)
            safe = _safe_contact(contact)
            candidate = {
                "contact_id": contact_id,
                "display_name": safe.get("display_name"),
                "persona": safe.get("persona"),
                "buying_role": safe.get("buying_role"),
                "associated_companies": [
                    {
                        "company_id": company.get("company_id"),
                        "name": company.get("name"),
                        "country": company.get("country"),
                        "owner_id": company.get("owner_id"),
                    }
                    for company in scoped_companies
                ],
                "confidence_score": score,
                "confidence_band": _confidence_band(score),
                "evidence": evidence,
                "requires_human_confirmation": True,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
            }
            existing = by_id.get(contact_id)
            if not existing or candidate["confidence_score"] > existing["confidence_score"]:
                by_id[contact_id] = candidate
    return sorted(by_id.values(), key=lambda item: item["confidence_score"], reverse=True)[:limit]


def _photo_missing_clue_prompt(hints: dict[str, Any], contact_candidates: list[dict[str, Any]], company_candidates: list[dict[str, Any]]) -> str:
    if contact_candidates:
        top_score = contact_candidates[0].get("confidence_score", 0)
        close = [candidate for candidate in contact_candidates if top_score - candidate.get("confidence_score", 0) <= 10]
        if len(close) > 1:
            return "Which contact should I use?"
        return "Reply confirm with this contact/company before I prepare the HubSpot note and WhatsApp follow-up task."
    if company_candidates:
        return f"Which person at {company_candidates[0].get('name')} should I match?"
    if not hints.get("company_names"):
        return "company name?"
    if not hints.get("contact_names"):
        return "contact name?"
    return "which contact/company?"


def _next_business_day_10_sg(now: datetime | None = None) -> str:
    local = (now or datetime.now(timezone.utc)).astimezone(SINGAPORE_TIMEZONE)
    target_date = local.date() + timedelta(days=1)
    while target_date.weekday() >= 5:
        target_date += timedelta(days=1)
    return datetime.combine(target_date, datetime_time(10, 0), tzinfo=SINGAPORE_TIMEZONE).isoformat()


def _selected_match_company_id(selected_match: dict[str, Any]) -> str:
    company_id = str(selected_match.get("company_id") or "").strip()
    if company_id:
        return company_id
    companies = selected_match.get("associated_companies")
    if isinstance(companies, list) and companies:
        return str(companies[0].get("company_id") or "").strip()
    company = selected_match.get("company") if isinstance(selected_match.get("company"), dict) else {}
    return str(company.get("company_id") or company.get("id") or "").strip()


def _selected_match_company_name(selected_match: dict[str, Any], company: dict[str, Any]) -> str:
    props = company.get("properties", {})
    if selected_match.get("company_name"):
        return str(selected_match.get("company_name"))
    companies = selected_match.get("associated_companies")
    if isinstance(companies, list) and companies and companies[0].get("name"):
        return str(companies[0].get("name"))
    return str(props.get("name") or "the account")


def _photo_followup_draft(contact_name: str, company_name: str, event_name: str) -> str:
    first = (contact_name or "").split(" ")[0] or "there"
    event_text = f" at {event_name}" if event_name else ""
    return (
        f"Hi {first}, good meeting you{event_text}. "
        f"Thought to follow up on how {company_name} is handling workforce ops. "
        "Would it be useful if I shared a few quick ideas?"
    )


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


def _policy_classification(email: str, policy: dict[str, Any]) -> str:
    normalized = _normalize_email(email)
    if normalized in policy["disabled"]:
        return "disabled"
    if normalized in policy["admins"]:
        return "admin"
    if normalized in policy["managers"]:
        return "manager"
    if normalized in policy["sales_reps"]:
        return "sales_rep"
    for rep in policy["sales_reps"].values():
        if normalized == rep.get("hubspot_owner_email"):
            return "sales_rep_owner_email"
    return "unclassified"


def _owner_name(owner: dict[str, Any]) -> str:
    first = str(owner.get("firstName") or "").strip()
    last = str(owner.get("lastName") or "").strip()
    full = " ".join(part for part in [first, last] if part).strip()
    return full or str(owner.get("email") or "").strip()


def _target_counts_for_owner(owner_id: str, countries: list[str]) -> dict[str, Any]:
    by_country: dict[str, int | None] = {}
    total = 0
    for country in countries:
        data = _company_search(_target_filters([country], owner_id), limit=1)
        count = data.get("total")
        by_country[country] = count
        if isinstance(count, int):
            total += count
    return {"total": total, "by_country": by_country}


def _read_crm_object(object_type: str, object_id: str, properties: list[str]) -> dict[str, Any] | None:
    if not object_id:
        return None
    try:
        return _get(f"/crm/v3/objects/{object_type}/{object_id}", {"properties": ",".join(properties)})
    except HubSpotError as error:
        if "404" in str(error):
            return None
        raise


def _read_marketing_contact(contact_id: str) -> dict[str, Any] | None:
    return _read_crm_object("contacts", str(contact_id), MARKETING_CONTACT_PROPERTIES)


def _read_marketing_company(company_id: str) -> dict[str, Any] | None:
    return _read_crm_object("companies", str(company_id), MARKETING_COMPANY_PROPERTIES)


def _email_domain(value: str) -> str:
    email = _safe_email(value)
    return email.split("@", 1)[1] if "@" in email else ""


def _contact_display_name(contact: dict[str, Any] | None) -> str:
    if not contact:
        return ""
    props = contact.get("properties", {})
    first = str(props.get("firstname") or "").strip()
    last = str(props.get("lastname") or "").strip()
    full = " ".join(part for part in [first, last] if part).strip()
    return full or str(props.get("jobtitle") or "").strip()


def _safe_marketing_contact_summary(contact: dict[str, Any] | None) -> dict[str, Any]:
    if not contact:
        return {}
    props = contact.get("properties", {})
    return {
        "contact_id": str(contact.get("id") or ""),
        "display_name": _contact_display_name(contact),
        "jobtitle": props.get("jobtitle") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "email_domain": _email_domain(str(props.get("email") or "")),
        "lifecycle_stage": props.get("lifecyclestage") or "",
        "created_at": props.get("createdate") or "",
        "last_modified_at": props.get("lastmodifieddate") or "",
    }


def _safe_marketing_company_summary(company: dict[str, Any] | None) -> dict[str, Any]:
    if not company:
        return {}
    props = company.get("properties", {})
    return {
        "company_id": str(company.get("id") or ""),
        "hubspot_scoped": True,
        "scope_source": SCOPE_SOURCE,
        "name": props.get("name") or "",
        "domain": props.get("domain") or "",
        "country": props.get("company_country") or "",
        "owner_id": props.get("hubspot_owner_id") or "",
        "target_account": str(props.get("hs_is_target_account") or "").lower() == "true",
        "campaign": props.get("campaign") or "",
    }


def _has_marketing_company_access(company: dict[str, Any], scope: dict[str, Any]) -> bool:
    props = company.get("properties", {})
    country = props.get("company_country") or ""
    owner_id = str(props.get("hubspot_owner_id") or "")
    if scope["kind"] == "admin":
        return True
    if scope["kind"] == "manager":
        return not country or country in scope.get("countries", ())
    if scope["kind"] == "ae":
        return bool(country and country in scope.get("countries", ()) and owner_id and owner_id == str(scope.get("owner_id") or ""))
    return False


def _marketing_companies_for_contact(contact_id: str) -> list[dict[str, Any]]:
    company_ids = _association_ids("contacts", str(contact_id), "companies", 20)
    return _batch_read("companies", company_ids, MARKETING_COMPANY_PROPERTIES)


def _marketing_access_context_for_contact(contact_id: str, scope: dict[str, Any]) -> dict[str, Any]:
    contact = _read_marketing_contact(str(contact_id))
    companies = _marketing_companies_for_contact(str(contact_id)) if contact else []
    accessible_companies = [company for company in companies if _has_marketing_company_access(company, scope)]
    if scope["kind"] == "admin":
        allowed = True
    elif accessible_companies:
        allowed = True
    elif scope["kind"] == "manager" and contact and not companies:
        allowed = True
    else:
        allowed = False
    return {
        "allowed": allowed,
        "contact": contact,
        "companies": accessible_companies if accessible_companies else ([] if scope["kind"] != "admin" else companies),
        "scope_status": "company_scoped" if accessible_companies else "unresolved_company_scope",
    }


def _marketing_access_context_for_thread(thread: dict[str, Any], scope: dict[str, Any]) -> dict[str, Any]:
    contact_id = str(thread.get("associatedContactId") or "")
    context = _marketing_access_context_for_contact(contact_id, scope) if contact_id else {
        "allowed": scope["kind"] in {"admin", "manager"},
        "contact": None,
        "companies": [],
        "scope_status": "unresolved_company_scope",
    }
    if contact_id and not context.get("contact") and not context.get("companies") and scope["kind"] in {"admin", "manager"}:
        context["allowed"] = True
        context["scope_status"] = "unresolved_company_scope"
    context["thread"] = thread
    context["associated_contact_id"] = contact_id
    context["associated_ticket_id"] = str(thread.get("threadAssociations", {}).get("associatedTicketId") or "")
    return context


def _default_latest_message_after() -> str:
    start = datetime.now(timezone.utc) - timedelta(days=30)
    return start.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _conversation_threads(params: dict[str, str], limit: int) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT)
    results: list[dict[str, Any]] = []
    next_after = params.get("after", "")
    while len(results) < requested_limit:
        page_params = {key: value for key, value in params.items() if value != ""}
        page_params["limit"] = str(min(100, requested_limit - len(results)))
        if next_after:
            page_params["after"] = str(next_after)
        page = _get("/conversations/v3/conversations/threads", page_params)
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _conversation_messages(thread_id: str, limit: int) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=INBOUND_MESSAGE_RETURN_LIMIT)
    results: list[dict[str, Any]] = []
    next_after = ""
    while len(results) < requested_limit:
        page_params = {"limit": str(min(100, requested_limit - len(results)))}
        if next_after:
            page_params["after"] = next_after
        page = _get(f"/conversations/v3/conversations/threads/{thread_id}/messages", page_params)
        page_results = page.get("results", [])
        results.extend(page_results)
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not page_results or not next_after:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _thread_sort_value(thread: dict[str, Any]) -> str:
    return str(thread.get("latestMessageTimestamp") or thread.get("latestMessageReceivedTimestamp") or thread.get("createdAt") or "")


def _safe_thread_summary(thread: dict[str, Any], access_context: dict[str, Any]) -> dict[str, Any]:
    contact = _safe_marketing_contact_summary(access_context.get("contact"))
    companies = [_safe_marketing_company_summary(company) for company in access_context.get("companies", [])]
    return {
        "thread_id": str(thread.get("id") or ""),
        "status": thread.get("status") or "",
        "inbox_id": thread.get("inboxId") or "",
        "original_channel_id": thread.get("originalChannelId") or "",
        "original_channel_account_id": thread.get("originalChannelAccountId") or "",
        "assigned_to": thread.get("assignedTo") or "",
        "created_at": thread.get("createdAt") or "",
        "latest_message_at": thread.get("latestMessageTimestamp") or "",
        "latest_received_at": thread.get("latestMessageReceivedTimestamp") or "",
        "latest_sent_at": thread.get("latestMessageSentTimestamp") or "",
        "associated_contact_id": access_context.get("associated_contact_id") or "",
        "associated_ticket_id": access_context.get("associated_ticket_id") or "",
        "contact": contact,
        "companies": companies,
        "scope_status": access_context.get("scope_status") or "",
        "spam": bool(thread.get("spam")),
        "archived": bool(thread.get("archived")),
    }


def _message_text(message: dict[str, Any]) -> tuple[str, bool]:
    raw = str(message.get("text") or "")
    if not raw and message.get("richText"):
        raw = _html_to_text(str(message.get("richText") or ""))
    text = re.sub(r"\s+", " ", raw).strip()
    if len(text) > MESSAGE_TEXT_LIMIT:
        return text[:MESSAGE_TEXT_LIMIT].rstrip(), True
    return text, False


def _safe_thread_message(message: dict[str, Any]) -> dict[str, Any]:
    text, local_truncated = _message_text(message)
    truncation_status = str(message.get("truncationStatus") or "")
    return {
        "message_id": str(message.get("id") or ""),
        "type": message.get("type") or "",
        "direction": message.get("direction") or "",
        "status": message.get("status") or "",
        "created_at": message.get("createdAt") or message.get("created_at") or "",
        "sent_at": message.get("sentAt") or message.get("sent_at") or "",
        "sender_actor_id": message.get("senderActorId") or message.get("sender_actor_id") or "",
        "actor_id": message.get("actorId") or "",
        "recipients": message.get("recipients") or [],
        "text": text,
        "text_truncated": bool(local_truncated or truncation_status in {"TRUNCATED", "TRUNCATED_TO_MOST_RECENT_REPLY"}),
        "truncation_status": truncation_status,
        "attachment_count": len(message.get("attachments", []) or []),
    }


def _marketing_signal_fields(props: dict[str, Any]) -> dict[str, str]:
    keys = [
        "campaign",
        "abm_campaign_tag",
        "ad_interaction",
        "utm_campaign",
        "hs_analytics_source",
        "hs_analytics_source_data_1",
        "hs_analytics_source_data_2",
        "hs_latest_source",
        "hs_latest_source_data_1",
        "hs_latest_source_data_2",
        "first_conversion_event_name",
        "first_conversion_date",
        "recent_conversion_event_name",
        "recent_conversion_date",
    ]
    return {key: str(props.get(key) or "") for key in keys if str(props.get(key) or "").strip()}


def _campaign_summary(campaign: dict[str, Any]) -> dict[str, Any]:
    props = campaign.get("properties", {})
    return {
        "campaign_id": str(campaign.get("id") or campaign.get("campaignGuid") or props.get("hs_object_id") or ""),
        "name": props.get("hs_name") or campaign.get("name") or "",
        "status": props.get("hs_campaign_status") or "",
        "start_date": props.get("hs_start_date") or "",
        "end_date": props.get("hs_end_date") or "",
        "audience": props.get("hs_audience") or "",
        "utm": props.get("hs_utm") or "",
        "owner_id": props.get("hs_owner") or "",
        "created_at": campaign.get("createdAt") or "",
        "updated_at": campaign.get("updatedAt") or "",
    }


def _campaign_matches_filters(campaign: dict[str, Any], status: str = "", start_date: str = "", end_date: str = "") -> bool:
    props = campaign.get("properties", {})
    if status and str(props.get("hs_campaign_status") or "").lower() != status.lower():
        return False
    campaign_start = str(props.get("hs_start_date") or "")
    campaign_end = str(props.get("hs_end_date") or "")
    if start_date and campaign_end and campaign_end < start_date:
        return False
    if end_date and campaign_start and campaign_start > end_date:
        return False
    return True


def _marketing_campaign_search(name: str = "", status: str = "", start_date: str = "", end_date: str = "", limit: int = 20) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=20, maximum=MARKETING_CAMPAIGN_RETURN_LIMIT)
    params = {
        "limit": str(min(100, requested_limit)),
        "properties": ",".join(CAMPAIGN_PROPERTIES),
        "sort": "-updatedAt",
    }
    if name:
        params["name"] = name
    results: list[dict[str, Any]] = []
    next_after = ""
    while len(results) < requested_limit:
        page_params = dict(params)
        page_params["limit"] = str(min(100, requested_limit - len(results)))
        if next_after:
            page_params["after"] = next_after
        page = _get("/marketing/v3/campaigns", page_params)
        for campaign in page.get("results", []):
            if _campaign_matches_filters(campaign, status, start_date, end_date):
                results.append(campaign)
                if len(results) >= requested_limit:
                    break
        next_after = str(page.get("paging", {}).get("next", {}).get("after") or "")
        if not next_after or len(results) >= requested_limit:
            break
    return {
        "results": results,
        "requested_limit": requested_limit,
        "returned_count": len(results),
        "has_more": bool(next_after),
        "truncated": bool(next_after),
    }


def _get_campaign(campaign_id: str) -> dict[str, Any]:
    return _get(f"/marketing/v3/campaigns/{campaign_id}", {"properties": ",".join(CAMPAIGN_PROPERTIES)})


def _safe_asset_summary(asset_type: str, asset: dict[str, Any]) -> dict[str, Any]:
    props = asset.get("properties", {}) if isinstance(asset.get("properties"), dict) else {}
    metrics = asset.get("metrics") or asset.get("performanceMetrics") or props.get("metrics") or {}
    return {
        "asset_type": asset_type,
        "asset_id": str(asset.get("id") or asset.get("assetId") or props.get("hs_object_id") or ""),
        "name": asset.get("name") or asset.get("title") or props.get("hs_name") or props.get("name") or "",
        "url": asset.get("url") or props.get("url") or "",
        "metrics_available": asset_type not in NO_METRIC_CAMPAIGN_ASSET_TYPES and bool(metrics),
        "metrics": metrics if isinstance(metrics, dict) else {},
    }


def _campaign_assets(campaign_id: str, asset_types: list[str] | None = None, start_date: str = "", end_date: str = "", limit: int = 50) -> dict[str, Any]:
    requested_limit = _bounded_int(limit, default=50, maximum=CAMPAIGN_ASSET_RETURN_LIMIT)
    selected_types = []
    for asset_type in asset_types or list(MARKETING_CAMPAIGN_ASSET_TYPES):
        normalized = str(asset_type or "").strip().upper()
        if normalized in MARKETING_CAMPAIGN_ASSET_TYPES and normalized not in selected_types:
            selected_types.append(normalized)
    assets_by_type: dict[str, Any] = {}
    truncated = False
    for asset_type in selected_types:
        params = {"limit": str(requested_limit)}
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        page = _get(f"/marketing/v3/campaigns/{campaign_id}/assets/{asset_type}", params)
        raw_assets = page.get("results", []) if isinstance(page.get("results"), list) else []
        has_more = bool(page.get("paging", {}).get("next", {}).get("after"))
        truncated = truncated or has_more or len(raw_assets) > requested_limit
        assets_by_type[asset_type] = {
            "assets": [_safe_asset_summary(asset_type, asset) for asset in raw_assets[:requested_limit]],
            "returned_count": min(len(raw_assets), requested_limit),
            "has_more": has_more,
            "truncated": has_more or len(raw_assets) > requested_limit,
            "metrics_caveat": "No metrics available for this HubSpot campaign asset type."
            if asset_type in NO_METRIC_CAMPAIGN_ASSET_TYPES
            else "",
        }
    return {
        "asset_types": selected_types,
        "assets_by_type": assets_by_type,
        "requested_limit": requested_limit,
        "has_more": truncated,
        "truncated": truncated,
    }


def _require_marketing_manager_or_admin(scope: dict[str, Any], slack_user_email: str) -> dict[str, Any] | None:
    if scope["kind"] in {"admin", "manager"}:
        return None
    return _blocked(
        "HubSpot marketing and campaign lookups require manager/admin scope unless a scoped company/contact context is supplied.",
        {"caller_email": slack_user_email},
    )


def _candidate_campaign_query(contact: dict[str, Any] | None, companies: list[dict[str, Any]], explicit_query: str = "") -> str:
    if explicit_query:
        return explicit_query
    if contact:
        props = contact.get("properties", {})
        for key in ("utm_campaign", "abm_campaign_tag", "recent_conversion_event_name", "first_conversion_event_name"):
            value = str(props.get(key) or "").strip()
            if value:
                return value
    for company in companies:
        props = company.get("properties", {})
        for key in ("campaign", "utm_campaign", "abm_campaign_tag"):
            value = str(props.get(key) or "").strip()
            if value:
                return value
    return ""


@mcp.tool()
def list_inbound_threads(
    slack_user_email: str,
    thread_status: str = "OPEN",
    inbox_id: str = "",
    associated_contact_id: str = "",
    latest_message_after: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """List recent HubSpot Conversations inbox threads with summaries only."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        params = {
            "association": "TICKET",
            "archived": "false",
            "sort": "latestMessageTimestamp",
            "latestMessageTimestampAfter": latest_message_after or _default_latest_message_after(),
            "inboxId": str(inbox_id or ""),
            "associatedContactId": str(associated_contact_id or ""),
        }
        fetch_limit = min(INBOUND_THREAD_RETURN_LIMIT, max(_bounded_int(limit, default=20), 20))
        data = _conversation_threads(params, fetch_limit)
        requested_status = str(thread_status or "").strip().upper()
        summaries = []
        inaccessible_count = 0
        unresolved_scope_count = 0
        for thread in sorted(data.get("results", []), key=_thread_sort_value, reverse=True):
            if requested_status and requested_status != "ANY" and str(thread.get("status") or "").upper() != requested_status:
                continue
            access_context = _marketing_access_context_for_thread(thread, scope)
            if not access_context["allowed"]:
                inaccessible_count += 1
                continue
            if access_context.get("scope_status") == "unresolved_company_scope":
                unresolved_scope_count += 1
            summaries.append(_safe_thread_summary(thread, access_context))
            if len(summaries) >= _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT):
                break
        return {
            "answer": summaries,
            "source": "HubSpot Conversations threads API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_status": requested_status or "ANY",
                "inbox_id": inbox_id,
                "associated_contact_id": associated_contact_id,
                "latest_message_after": params["latestMessageTimestampAfter"],
            },
            "requested_limit": _bounded_int(limit, default=20, maximum=INBOUND_THREAD_RETURN_LIMIT),
            "scanned_count": len(data.get("results", [])),
            "returned_count": len(summaries),
            "has_more": data.get("has_more"),
            "truncated": bool(data.get("truncated") or inaccessible_count or unresolved_scope_count),
            "confidence": "needs-check" if data.get("truncated") or unresolved_scope_count else "verified",
            "caveat": (
                "Summaries only. Use get_inbound_thread_context for one selected thread's full text; "
                "bulk full-thread exports and phone/contact exports are intentionally not returned."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_inbound_thread_context(slack_user_email: str, thread_id: str, message_limit: int = 100) -> dict[str, Any]:
    """Read one selected HubSpot Conversations inbox thread, including full message text."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        thread = _get(f"/conversations/v3/conversations/threads/{thread_id}", {"association": "TICKET"})
        access_context = _marketing_access_context_for_thread(thread, scope)
        if not access_context["allowed"]:
            return _blocked("Thread is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "thread_id": thread_id})
        message_data = _conversation_messages(str(thread_id), message_limit)
        messages = [_safe_thread_message(message) for message in message_data.get("results", [])]
        text_truncated = any(message.get("text_truncated") for message in messages)
        return {
            "answer": {
                "thread": _safe_thread_summary(thread, access_context),
                "messages": messages,
                "message_count": len(messages),
                "full_text_scope": "single_selected_thread_only",
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Conversations thread and messages API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_id": str(thread_id),
                "message_limit": _bounded_int(message_limit, default=100, maximum=INBOUND_MESSAGE_RETURN_LIMIT),
            },
            "requested_limit": message_data.get("requested_limit"),
            "returned_count": message_data.get("returned_count"),
            "has_more": message_data.get("has_more"),
            "truncated": bool(message_data.get("truncated") or text_truncated),
            "confidence": "needs-check" if message_data.get("truncated") or text_truncated else "verified",
            "caveat": "Full text is returned for this one selected thread only. Attachments are counted but not fetched, and no HubSpot mutation or external message send is performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "thread_id": thread_id})


@mcp.tool()
def list_marketing_campaigns(
    slack_user_email: str,
    name: str = "",
    status: str = "",
    start_date: str = "",
    end_date: str = "",
    limit: int = 20,
) -> dict[str, Any]:
    """List HubSpot marketing campaigns for manager/admin campaign triage."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        data = _marketing_campaign_search(name, status, start_date, end_date, limit)
        campaigns = [_campaign_summary(campaign) for campaign in data.get("results", [])]
        return {
            "answer": campaigns,
            "source": "HubSpot Marketing Campaigns API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "name": name,
                "status": status,
                "start_date": start_date,
                "end_date": end_date,
            },
            **_search_metadata(data),
            "confidence": "needs-check" if data.get("truncated") else "verified",
            "caveat": "Read-only campaign metadata. Use get_campaign_assets for associated forms, pages, emails, SMS/social, and podcast episodes.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def get_campaign_assets(
    slack_user_email: str,
    campaign_id: str,
    asset_types: list[str] | None = None,
    start_date: str = "",
    end_date: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Read HubSpot campaign assets and available metrics for selected asset types."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        blocked = _require_marketing_manager_or_admin(scope, slack_user_email)
        if blocked:
            return blocked
        campaign = _get_campaign(str(campaign_id))
        asset_data = _campaign_assets(str(campaign_id), asset_types, start_date, end_date, limit)
        includes_no_metric_assets = any(asset_type in NO_METRIC_CAMPAIGN_ASSET_TYPES for asset_type in asset_data.get("asset_types", []))
        return {
            "answer": {
                "campaign": _campaign_summary(campaign),
                **asset_data,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Marketing Campaigns assets API",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "campaign_id": str(campaign_id),
                "start_date": start_date,
                "end_date": end_date,
            },
            "confidence": "needs-check" if asset_data.get("truncated") or includes_no_metric_assets else "verified",
            "caveat": "Podcast episodes and several HubSpot campaign asset types have no metrics available; association evidence is not proof of contact engagement.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "campaign_id": campaign_id})


@mcp.tool()
def get_marketing_touch_context(
    slack_user_email: str,
    thread_id: str = "",
    contact_id: str = "",
    company_id: str = "",
    campaign_id: str = "",
    campaign_name: str = "",
    include_recent_threads: bool = True,
) -> dict[str, Any]:
    """Combine scoped inbound, contact/company source fields, campaign, and podcast association context."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if not any([thread_id, contact_id, company_id, campaign_id, campaign_name]):
            return _blocked("Provide a thread_id, contact_id, company_id, campaign_id, or campaign_name.", {"caller_email": slack_user_email})

        thread_summary: dict[str, Any] = {}
        contact: dict[str, Any] | None = None
        companies: list[dict[str, Any]] = []

        if thread_id:
            thread = _get(f"/conversations/v3/conversations/threads/{thread_id}", {"association": "TICKET"})
            access_context = _marketing_access_context_for_thread(thread, scope)
            if not access_context["allowed"]:
                return _blocked("Thread is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "thread_id": thread_id})
            thread_summary = _safe_thread_summary(thread, access_context)
            contact = access_context.get("contact")
            companies = access_context.get("companies", [])
            contact_id = contact_id or str(access_context.get("associated_contact_id") or "")

        if contact_id and contact is None:
            contact_access = _marketing_access_context_for_contact(str(contact_id), scope)
            if not contact_access["allowed"]:
                return _blocked("Contact is outside caller scope or has no scoped company context.", {"caller_email": slack_user_email, "contact_id": contact_id})
            contact = contact_access.get("contact")
            companies = contact_access.get("companies", [])

        if company_id:
            company = _read_marketing_company(str(company_id))
            if not company or not _has_marketing_company_access(company, scope):
                return _blocked("Company is outside caller marketing scope.", {"caller_email": slack_user_email, "company_id": company_id})
            if str(company.get("id") or "") not in {str(item.get("id") or "") for item in companies}:
                companies.append(company)

        recent_threads = []
        if include_recent_threads and contact_id:
            recent_data = _conversation_threads(
                {
                    "associatedContactId": str(contact_id),
                    "association": "TICKET",
                    "archived": "false",
                    "sort": "latestMessageTimestamp",
                    "latestMessageTimestampAfter": _default_latest_message_after(),
                },
                5,
            )
            for recent_thread in sorted(recent_data.get("results", []), key=_thread_sort_value, reverse=True):
                recent_access = _marketing_access_context_for_thread(recent_thread, scope)
                if recent_access["allowed"]:
                    recent_threads.append(_safe_thread_summary(recent_thread, recent_access))

        contact_source_fields = _marketing_signal_fields(contact.get("properties", {})) if contact else {}
        company_source_fields = [
            {
                "company_id": str(company.get("id") or ""),
                "fields": _marketing_signal_fields(company.get("properties", {})),
            }
            for company in companies
        ]

        campaign_query = _candidate_campaign_query(contact, companies, campaign_name)
        campaigns = []
        podcast_assets = []
        selected_campaign_ids = [str(campaign_id)] if campaign_id else []
        if campaign_query and not selected_campaign_ids:
            campaign_data = _marketing_campaign_search(campaign_query, limit=3)
            selected_campaign_ids = [str(campaign.get("id") or "") for campaign in campaign_data.get("results", []) if campaign.get("id")]
            campaigns.extend([_campaign_summary(campaign) for campaign in campaign_data.get("results", [])])
        if campaign_id:
            campaign = _get_campaign(str(campaign_id))
            campaigns.append(_campaign_summary(campaign))
        for selected_campaign_id in selected_campaign_ids[:3]:
            asset_data = _campaign_assets(selected_campaign_id, ["PODCAST_EPISODE"], limit=20)
            podcast_assets.append(
                {
                    "campaign_id": selected_campaign_id,
                    "assets": asset_data.get("assets_by_type", {}).get("PODCAST_EPISODE", {}).get("assets", []),
                    "metrics_caveat": "HubSpot Campaigns API reports no metrics for PODCAST_EPISODE assets.",
                }
            )

        return {
            "answer": {
                "thread": thread_summary,
                "contact": _safe_marketing_contact_summary(contact),
                "companies": [_safe_marketing_company_summary(company) for company in companies],
                "contact_source_fields": contact_source_fields,
                "company_source_fields": company_source_fields,
                "recent_threads": recent_threads,
                "campaigns": campaigns,
                "podcast_campaign_evidence": podcast_assets,
                "will_mutate_hubspot": False,
            },
            "source": "HubSpot Conversations, CRM, and Marketing Campaigns APIs",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "thread_id": thread_id,
                "contact_id": contact_id,
                "company_id": company_id,
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
            },
            "confidence": "needs-check",
            "caveat": "Marketing source fields and podcast campaign assets are attribution signals. Podcast asset association is not proof of contact engagement, and no HubSpot mutation or external message send is performed.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def audit_hubspot_owner_roster(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    """List active HubSpot owners and target-account counts for admin classification."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] != "admin":
            return _blocked("Only admins can audit the HubSpot owner roster for NurtureAny classification.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        policy = _access_policy()
        owners = _list_owners(limit)
        roster = []
        for owner in owners:
            email = _normalize_email(str(owner.get("email") or ""))
            if not email:
                continue
            owner_id = str(owner.get("id") or "")
            counts = _target_counts_for_owner(owner_id, selected)
            roster.append(
                {
                    "owner_id": owner_id,
                    "email": email,
                    "name": _owner_name(owner),
                    "classification": _policy_classification(email, policy),
                    "target_account_counts": counts,
                }
            )
        unclassified_count = len([owner for owner in roster if owner["classification"] == "unclassified"])
        return {
            "answer": {
                "owners": roster,
                "owner_count": len(roster),
                "unclassified_count": unclassified_count,
                "policy_source": policy["source"],
            },
            "source": "HubSpot owners API and target-account counts",
            "scope": _scope_response(scope, selected),
            "confidence": "needs-check" if unclassified_count else "verified",
            "caveat": "Audit is admin-only and for classification; it does not grant access by itself.",
        }
    except AccessPolicyError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def list_my_target_accounts(slack_user_email: str, limit: int = 20, query: str | None = None) -> dict[str, Any]:
    """List target accounts owned by the requesting AE."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked" or not scope.get("owner_id"):
            return _blocked("Slack email is not mapped to a HubSpot owner.", {"caller_email": slack_user_email})
        countries = list(scope["countries"])
        data = _company_search(_target_filters(countries, scope["owner_id"]), limit, query=query)
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
    query: str | None = None,
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
        data = _company_search(_target_filters(selected, target_owner_id), limit, query=query)
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
def find_target_accounts_by_luma_match_keys(
    slack_user_email: str,
    email_domains: list[str] | None = None,
    company_name_candidates: list[str] | None = None,
    countries: list[str] | None = None,
    limit: int = LUMA_MATCH_RETURN_LIMIT,
    owner_email: str | None = None,
) -> dict[str, Any]:
    """Find scoped HubSpot target accounts from safe Luma attendee match keys.

    Use after get_luma_event_match_keys. This avoids paging every target account
    for event-wide questions while still enforcing HubSpot target-account,
    country, owner, and caller scope before any Luma guest details are shown.
    """

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = _bounded_int(limit, default=LUMA_MATCH_RETURN_LIMIT, maximum=LUMA_MATCH_RETURN_LIMIT)
        raw_domains = [domain for value in (email_domains or []) if (domain := _normalize_domain_key(value))]
        raw_names = [name for value in (company_name_candidates or []) if (name := _normalize_company_name_key(value))]
        domains = _unique_values(raw_domains)[:LUMA_MATCH_DOMAIN_LIMIT]
        names = _unique_values(raw_names)[:LUMA_MATCH_NAME_LIMIT]
        if not domains and not names:
            return _blocked("No safe Luma match keys were provided.", _scope_response(scope, selected, target_owner_id, target_owner_email))

        candidates: dict[str, dict[str, Any]] = {}
        any_truncated = len(_unique_values(raw_domains)) > len(domains) or len(_unique_values(raw_names)) > len(names)
        base_filters = _target_filters(selected, target_owner_id)

        for domain in domains:
            if len(candidates) >= requested_limit:
                any_truncated = True
                break
            data = _company_search(base_filters + [{"propertyName": "domain", "operator": "EQ", "value": domain}], limit=5)
            any_truncated = any_truncated or bool(data.get("truncated"))
            for company in data.get("results", []):
                _add_luma_candidate(candidates, company, "exact_email_domain", domain, "verified")

        for name in names:
            if len(candidates) >= requested_limit:
                any_truncated = True
                break
            data = _company_search(
                base_filters + [{"propertyName": "name", "operator": "CONTAINS_TOKEN", "value": name}],
                limit=5,
            )
            any_truncated = any_truncated or bool(data.get("truncated"))
            for company in data.get("results", []):
                _add_luma_candidate(candidates, company, "company_name_candidate", name, "needs-check")

        answer = list(candidates.values())[:requested_limit]
        return {
            "answer": answer,
            "source": "HubSpot target-account lookup from Luma safe match keys",
            "scope": {
                **_scope_response(scope, selected, target_owner_id, target_owner_email),
                "email_domain_key_count": len(domains),
                "company_name_candidate_count": len(names),
                "requested_limit": requested_limit,
            },
            "total": len(answer),
            "requested_limit": requested_limit,
            "returned_count": len(answer),
            "has_more": any_truncated or len(candidates) > requested_limit,
            "truncated": any_truncated or len(candidates) > requested_limit,
            "confidence": "needs-check"
            if any_truncated or any(account.get("luma_match_confidence") == "needs-check" for account in answer)
            else "verified",
            "caveat": (
                "This is event-first HubSpot scoping from safe Luma match keys. "
                "Domain matches are stronger; company-name candidates need review. "
                "No raw Luma attendees, emails, phone numbers, or registration answers are returned."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def audit_priority_account_coverage(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
) -> dict[str, Any]:
    """Audit locked target-account coverage, double tap, stale/dirty accounts, and open follow-up tasks."""

    try:
        return _priority_account_coverage(
            slack_user_email=slack_user_email,
            countries=countries,
            owner_email=owner_email,
            week_start=week_start,
            week_end=week_end,
            limit=limit,
        )
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def build_friday_sales_review(
    slack_user_email: str,
    countries: list[str] | None = None,
    owner_email: str | None = None,
    week_start: str = "",
    week_end: str = "",
    limit: int = PRIORITY_ACCOUNT_RETURN_LIMIT,
) -> dict[str, Any]:
    """Build the manager Friday sales review for the tactical pause operating rhythm."""

    try:
        coverage = _priority_account_coverage(
            slack_user_email=slack_user_email,
            countries=countries,
            owner_email=owner_email,
            week_start=week_start,
            week_end=week_end,
            limit=limit,
            manager_only=True,
            include_internal=True,
        )
        if coverage.get("confidence") == "blocked":
            return coverage

        internal = coverage.pop("_internal", {})
        owner_rows = coverage.get("answer", {}).get("owners", [])
        stage_config = _friday_review_stage_config()
        deal_counts = _deal_counts_for_friday(
            internal.get("companies", []),
            internal.get("company_deal_ids", {}),
            internal.get("week", {}),
            stage_config,
        )
        answer = {
            "hygiene_summary": _friday_hygiene_summary(owner_rows),
            "funnel_snapshot": _friday_funnel_snapshot(owner_rows, deal_counts),
            "coaching_observations": _coaching_observations(owner_rows),
            "next_week_actions": _next_week_actions(owner_rows),
            "support_needed": _support_needed(coverage, deal_counts),
        }
        confidence = "verified"
        if coverage.get("confidence") == "needs-check" or deal_counts.get("confidence") == "needs-check":
            confidence = "needs-check"
        return {
            "answer": answer,
            "source": "HubSpot target-account coverage, safe calls/meetings/activity evidence, and configured deal funnel stages",
            "scope": coverage.get("scope", {}),
            "total": coverage.get("total"),
            "requested_limit": coverage.get("requested_limit"),
            "returned_count": coverage.get("returned_count"),
            "has_more": coverage.get("has_more"),
            "truncated": coverage.get("truncated"),
            "confidence": confidence,
            "caveat": (
                coverage.get("caveat", "")
                + " "
                + deal_counts.get("caveat", "")
                + " Friday report follows tactical pause guardrails: 120/150 account coverage, double tap, 40 connected calls, warm activity proof, QO/QO Met guardrail, and next-week correction."
            ).strip(),
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
        decision_status = context.get("coverage", {}).get("decision_maker_coverage", {}).get("status")
        return {
            "answer": context,
            "source": (
                "HubSpot company, contact, deal, and sales-owned task associations + Customer 360 link"
                if context["company"].get("c360_url")
                else "HubSpot company, contact, deal, and sales-owned task associations"
            ),
            "scope": _scope_response(scope, [context["company"]["country"]]),
            "confidence": "verified" if decision_status == "verified" and not context["company"].get("missing_fields") else "needs-check",
            "caveat": "Contact details and sales-owned follow-up tasks are summarized; raw phone numbers, task bodies, and exports are omitted.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_id": company_id})


@mcp.tool()
def build_pre_demo_game_plans(slack_user_email: str, company_ids: list[str], limit: int = PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT) -> dict[str, Any]:
    """Build game plans for selected HubSpot IDs, links, or exact company names."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        requested_limit = _bounded_int(limit, default=PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT, maximum=PRE_DEMO_GAME_PLAN_ACCOUNT_LIMIT)
        resolution = _resolve_pre_demo_company_refs(company_ids, scope, requested_limit)
        normalized_ids = resolution["company_ids"]
        if not normalized_ids and not resolution["ambiguous_matches"] and not resolution["not_found"]:
            return _blocked(
                "Provide selected HubSpot company IDs, company links, or exact company names before building pre-demo game plans.",
                {"caller_email": slack_user_email},
            )

        if resolution["ambiguous_matches"] or resolution["not_found"]:
            return {
                "answer": {
                    "message": "I could not safely resolve every selected account. Pick one of the scoped HubSpot company IDs below, or send a HubSpot company link.",
                    "resolved_matches": resolution["resolved_matches"],
                    "ambiguous_matches": resolution["ambiguous_matches"],
                    "not_found": resolution["not_found"],
                },
                "source": "HubSpot scoped target-account name search",
                "scope": _scope_response(scope, list(scope.get("countries", ()))),
                "total": resolution["input_count"],
                "requested_limit": requested_limit,
                "returned_count": 0,
                "has_more": resolution["truncated"],
                "truncated": resolution["truncated"],
                "missing_evidence": ["unresolved company selection"],
                "confidence": "blocked",
                "caveat": "Company-name matching is scoped to HubSpot target accounts and will not guess when the name is ambiguous or missing.",
            }

        selected_ids = normalized_ids[:requested_limit]
        plans = []
        countries: list[str] = []
        for company_id in selected_ids:
            context = _company_context(company_id, scope)
            if context is None:
                raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
            country = context.get("company", {}).get("country")
            if country and country not in countries:
                countries.append(country)
            plans.append(_build_pre_demo_game_plan_row(context))

        truncated = bool(resolution["truncated"])
        missing_evidence = sorted({item for plan in plans for item in plan.get("missing_evidence", [])})
        return {
            "answer": plans,
            "source": "HubSpot scoped account context and NurtureAny pre-demo game-plan playbook",
            "scope": _scope_response(scope, countries or list(scope.get("countries", ()))),
            "total": resolution["input_count"],
            "requested_limit": requested_limit,
            "returned_count": len(plans),
            "has_more": truncated,
            "truncated": truncated,
            "resolved_matches": resolution["resolved_matches"],
            "missing_evidence": missing_evidence,
            "confidence": "needs-check" if truncated or missing_evidence else "verified",
            "caveat": (
                "On-demand Slack-first game plans only. Company names are resolved only against scoped HubSpot target accounts; ambiguous names require a pick. Pricing, current tool, lead source, meeting reason, and case studies are not invented; "
                "social/gated research stays manual-check unless user snippets are provided."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})


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
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
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
            return _list_sales_followup_tasks_from_task_search(
                scope,
                selected,
                requested_limit,
                target_owner_id,
                target_owner_email,
                due_start,
                due_end,
            )

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
def check_account_followup_status(
    slack_user_email: str,
    company_ids: list[str],
    since_at: str,
    until_at: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Check safe HubSpot follow-up status for selected scoped target accounts."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        since_dt = _datetime_value(since_at)
        if not since_dt:
            return _blocked("Provide a valid since_at timestamp for follow-up status checks.", {"caller_email": slack_user_email})
        until_dt = _datetime_value(until_at) if until_at else None
        if until_at and not until_dt:
            return _blocked("Provide a valid until_at timestamp or omit it.", {"caller_email": slack_user_email})
        if until_dt and until_dt < since_dt:
            return _blocked("until_at must be after since_at.", {"caller_email": slack_user_email})

        normalized_ids = _normalized_company_ids(company_ids)
        if not normalized_ids:
            return _blocked(
                "Provide selected HubSpot company IDs or company links before checking follow-up status.",
                {"caller_email": slack_user_email},
            )

        requested_limit = _bounded_int(limit, default=50, maximum=50)
        selected_ids = normalized_ids[:requested_limit]
        rows: list[dict[str, Any]] = []
        countries: list[str] = []
        for company_id in selected_ids:
            company = _assert_company_access(company_id, scope)
            company_country = str(company.get("properties", {}).get("company_country") or "")
            if company_country and company_country not in countries:
                countries.append(company_country)
            contact_ids = _association_ids("companies", company_id, "contacts", 50)
            deal_ids = _association_ids("companies", company_id, "deals", 20)
            rows.append(_account_followup_status(company, contact_ids, deal_ids, since_dt, until_dt))

        truncated = len(normalized_ids) > requested_limit
        needs_check = truncated or any(row.get("confidence") == "needs-check" for row in rows)
        scope_response = _scope_response(scope, countries or list(scope.get("countries", ())))
        scope_response["since_at"] = since_at
        if until_at:
            scope_response["until_at"] = until_at

        return {
            "answer": rows,
            "source": "HubSpot WhatsApp communications, notes, tasks, and scoped associations",
            "scope": scope_response,
            "total": len(normalized_ids),
            "requested_limit": requested_limit,
            "returned_count": len(rows),
            "has_more": truncated,
            "truncated": truncated,
            "confidence": "needs-check" if needs_check else "verified",
            "caveat": (
                "Read-only follow-up status. WhatsApp is read from HubSpot communications; raw WhatsApp bodies, note bodies, "
                "task bodies, phone numbers, unmatched event attendees, and secrets are omitted."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "company_ids": company_ids})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


def _event_followup_context(event: dict[str, Any], event_tags: list[str] | None) -> dict[str, Any]:
    return {
        "event": event,
        "event_tags": event_tags or [],
        "read_body_internal_only": True,
    }


def _event_status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"followed_up": 0, "scheduled": 0, "not_found": 0, "needs_check": 0}
    for row in rows:
        status = str(row.get("followup_status") or "needs_check")
        counts[status if status in counts else "needs_check"] += 1
    return counts


def _apply_attendance_match_quality(row: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    safe_row = dict(row)
    safe_row["event_attendance_match"] = {
        "match_confidence": match.get("match_confidence") or "needs-check",
        "match_reasons": match.get("match_reasons") or [],
        "attended_match_count": match.get("attended_match_count") or 0,
    }
    if match.get("match_confidence") == "needs-check":
        safe_row["followup_status"] = "needs_check"
        safe_row["confidence"] = "needs-check"
        safe_row["caveat"] = (
            "Attendance matched by candidate company-name evidence; HubSpot follow-up evidence is safe, but account match needs review."
        )
    return safe_row


def _event_country_scope(scope: dict[str, Any], country: str, location: str, event_tags: list[str] | None) -> list[str]:
    filters = _resolved_event_filters(country, "", location)
    selected_country = filters["country"]
    if not selected_country:
        for tag in event_tags or []:
            selected_country = _canonical_country(tag) or selected_country
            if selected_country:
                break
    return _safe_countries([selected_country] if selected_country else None, scope["countries"])


@mcp.tool()
def check_event_followup_status(
    slack_user_email: str,
    event_tags: list[str] | None = None,
    event_id: str = "",
    location: str = "",
    country: str = "",
    event_type: str = "",
    start: str = "",
    end: str = "",
    owner_email: str | None = None,
    since_at: str = "",
    until_at: str = "",
    limit: int = 50,
) -> dict[str, Any]:
    """Resolve Luma attendance, then check event-specific HubSpot/Eazybe follow-up status."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected_countries = _event_country_scope(scope, country, location, event_tags)
        if not selected_countries:
            return _blocked("Requested event country/location is outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)

        requested_limit = _bounded_int(limit, default=50, maximum=200)
        normalized_event_tags = _event_tag_filters(event_tags, country, event_type, location)
        events_has_more = False
        events_truncated = False
        if event_id:
            event = _single_luma_event(str(event_id).strip())
        else:
            events, events_has_more, events_truncated = _list_luma_events_for_followup(
                "",
                start,
                end,
                country,
                event_type,
                location,
                event_tags,
            )
            event = _latest_luma_event(events)
            if not event:
                return _blocked(
                    "No matching Luma event found for the requested tags/window.",
                    {
                        **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                        "event_tag_filters": normalized_event_tags,
                    },
                )

        event_start = _datetime_value(str(event.get("start_at") or ""))
        event_end = _datetime_value(str(event.get("end_at") or "")) or event_start
        since_dt = _datetime_value(since_at) or event_end
        if not since_dt:
            return _blocked(
                "Could not determine event end time; provide since_at.",
                {
                    **_scope_response(scope, selected_countries, target_owner_id, target_owner_email),
                    "event_id": event.get("event_id") or event_id,
                },
            )
        until_dt = _datetime_value(until_at) if until_at else None
        if until_at and not until_dt:
            return _blocked("Provide a valid until_at timestamp or omit it.", {"caller_email": slack_user_email})
        if until_dt and until_dt < since_dt:
            return _blocked("until_at must be after since_at.", {"caller_email": slack_user_email})

        guests, guests_has_more, guests_truncated = _list_luma_guests(str(event.get("event_id") or event_id))
        match_data = _matched_event_companies(guests, scope, selected_countries, target_owner_id)
        matches = match_data["matches"]
        matched_company_ids = sorted(matches.keys())
        selected_company_ids = matched_company_ids[:requested_limit]
        rows: list[dict[str, Any]] = []
        event_context = _event_followup_context(event, normalized_event_tags)
        for company_id in selected_company_ids:
            match = matches[company_id]
            company = match["company"]
            contact_ids = _association_ids("companies", company_id, "contacts", 50)
            deal_ids = _association_ids("companies", company_id, "deals", 20)
            row = _account_followup_status(company, contact_ids, deal_ids, since_dt, until_dt, event_context)
            rows.append(_apply_attendance_match_quality(row, match))

        truncated = (
            len(matched_company_ids) > requested_limit
            or bool(events_truncated)
            or bool(guests_truncated)
            or any(row.get("activity_truncated") for row in rows)
        )
        candidate_match = any(match.get("match_confidence") == "needs-check" for match in matches.values())
        unmatched_attendees = match_data["unmatched_attended_guest_count"] > 0
        needs_check = truncated or candidate_match or unmatched_attendees or any(row.get("confidence") == "needs-check" for row in rows)
        scope_response = _scope_response(scope, selected_countries, target_owner_id, target_owner_email)
        scope_response.update(
            {
                "event_tag_filters": normalized_event_tags,
                "event_id": event.get("event_id") or event_id,
                "since_at": since_dt.isoformat().replace("+00:00", "Z"),
            }
        )
        if until_at:
            scope_response["until_at"] = until_at

        return {
            "answer": {
                "event": event,
                "matched_target_account_count": len(matched_company_ids),
                "status_counts": _event_status_counts(rows),
                "accounts": rows,
                "match_summary": {
                    "attended_guest_count": match_data["attended_guest_count"],
                    "matched_guest_count": match_data["matched_guest_count"],
                    "unmatched_attended_guest_count": match_data["unmatched_attended_guest_count"],
                    "verified_match_count": match_data["verified_match_count"],
                    "candidate_match_count": match_data["candidate_match_count"],
                    "events_has_more": events_has_more,
                    "guests_has_more": guests_has_more,
                },
            },
            "source": "Luma checked-in attendance plus HubSpot/Eazybe WhatsApp communications, tasks, notes, and scoped associations",
            "scope": scope_response,
            "total": len(matched_company_ids),
            "requested_limit": requested_limit,
            "returned_count": len(rows),
            "has_more": len(matched_company_ids) > requested_limit or events_has_more or guests_has_more,
            "truncated": truncated,
            "confidence": "needs-check" if needs_check else "verified",
            "caveat": (
                "Read-only event follow-up status. WhatsApp bodies are inspected only inside the classifier for event-specific matching and are never returned; "
                "raw attendee lists, guest emails, phone numbers, note bodies, task bodies, and secrets are omitted."
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except LumaEventError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "source": "Luma"})
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
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
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

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))
        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        data = _company_search(_target_filters(selected, target_owner_id), limit)
        companies = data.get("results", [])
        company_ids = [str(company.get("id") or "") for company in companies if company.get("id")]
        contact_index = _batch_association_ids("companies", "contacts", company_ids)
        contact_detail_index = _safe_contact_index(contact_index)

        gaps = []
        for company in companies:
            company_id = str(company.get("id") or "")
            contacts = contact_detail_index.get(company_id, [])
            contact_count = len(contact_index.get(company_id, []))
            summary = _summarize_company_with_contacts(company, contacts, contact_count)
            missing = list(summary.get("missing_fields", []))
            gap_fields = {"associated contact", "decision maker", "persona", "channel fit"}
            if any(field in missing for field in gap_fields) or summary.get("enrichment_status") != "nurture_ready":
                gaps.append(
                    {
                        "company_id": summary.get("company_id"),
                        "name": summary.get("name"),
                        "country": summary.get("country"),
                        "enrichment_status": summary.get("enrichment_status"),
                        "missing_fields": missing,
                        "associated_contact_count": summary.get("associated_contact_count"),
                        "decision_maker_count": summary.get("decision_maker_count"),
                        "buying_role_contact_count": summary.get("buying_role_contact_count"),
                        "role_inferred_decision_maker_candidate_count": summary.get(
                            "role_inferred_decision_maker_candidate_count"
                        ),
                        "decision_maker_coverage": summary.get("decision_maker_coverage"),
                    }
                )
        metadata = _search_metadata(data)
        return {
            "answer": gaps,
            "source": "HubSpot target-account companies plus associated contact role and buying-role fields",
            "scope": _scope_response(scope, selected, target_owner_id, target_owner_email),
            "gap_count": len(gaps),
            "scored_account_count": metadata.get("returned_count", len(companies)),
            **metadata,
            "confidence": "needs-check" if metadata.get("truncated") or gaps else "verified",
            "caveat": _coverage_caveat(
                data,
                "Raw contact details are omitted; this is a coverage summary from HubSpot contact associations, persona fields, channel fit, and buying roles.",
            ),
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def find_t90_renewal_gaps(
    slack_user_email: str,
    countries: list[str] | None = None,
    limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
    owner_email: str | None = None,
    include_followup_tasks: bool = True,
    include_missing_renewal_dates: bool = True,
    missing_contract_end_date_limit: int = HUBSPOT_SEARCH_TOTAL_LIMIT,
) -> dict[str, Any]:
    """Find T-90 renewal target accounts and renewal-date classification gaps."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})

        selected = _safe_countries(countries, scope["countries"])
        if not selected:
            return _blocked("Requested countries are outside caller scope.", _scope_response(scope, []))

        target_owner_id, target_owner_email = _target_owner_id_for_scope(scope, owner_email)
        requested_limit = _bounded_int(limit, default=HUBSPOT_SEARCH_TOTAL_LIMIT, maximum=HUBSPOT_SEARCH_TOTAL_LIMIT)
        requested_missing_contract_end_date_limit = _bounded_int(
            missing_contract_end_date_limit,
            default=HUBSPOT_SEARCH_TOTAL_LIMIT,
            maximum=HUBSPOT_SEARCH_TOTAL_LIMIT,
        )
        today = datetime.now(timezone.utc).date()
        window_end = today + timedelta(days=90)
        data = _company_search_by_renewal_window(selected, target_owner_id, today, window_end, requested_limit)
        missing_data = (
            _company_search_missing_renewal_dates(
                selected,
                target_owner_id,
                requested_missing_contract_end_date_limit,
            )
            if include_missing_renewal_dates
            else {
                "results": [],
                "total": 0,
                "requested_limit": requested_missing_contract_end_date_limit,
                "returned_count": 0,
                "has_more": False,
                "truncated": False,
            }
        )

        task_index: dict[str, list[dict[str, Any]]] = {}
        task_metadata: dict[str, Any] = {}
        task_truncated = False
        task_lookup_skipped = False
        if include_followup_tasks and target_owner_id:
            task_context = _sales_followup_task_index_for_companies(
                data.get("results", []),
                target_owner_id,
                TASK_SEARCH_AIRTIGHT_RESULT_LIMIT,
            )
            task_index = task_context.get("tasks_by_company", {})
            task_metadata = task_context.get("metadata", {})
            task_truncated = bool(task_context.get("truncated"))
        elif include_followup_tasks:
            task_lookup_skipped = True

        renewing_company_ids = [str(company.get("id") or "") for company in data.get("results", []) if company.get("id")]
        renewing_contact_index = _batch_association_ids("companies", "contacts", renewing_company_ids)
        renewing_contact_detail_index = _safe_contact_index(renewing_contact_index)
        renewing_accounts = []
        gap_accounts = []
        for company in data.get("results", []):
            company_id = str(company.get("id") or "")
            summary = _summarize_company_with_contacts(
                company,
                renewing_contact_detail_index.get(company_id, []),
                len(renewing_contact_index.get(company_id, [])),
            )
            company_id = str(summary.get("company_id") or "")
            renewal_matches = _renewal_matches_in_window(company, today, window_end)
            if not renewal_matches:
                continue
            primary_renewal = renewal_matches[0]
            renewal = primary_renewal["date"]
            days_until_renewal = (renewal - today).days

            tasks = task_index.get(company_id, [])
            missing = list(summary.get("missing_fields", []))
            gap_reasons: list[str] = []
            if summary.get("enrichment_status") != "nurture_ready":
                gap_reasons.append(f"not nurture-ready ({summary.get('enrichment_status')})")
            if "decision maker" in missing:
                gap_reasons.append("missing decision-maker coverage")
            if include_followup_tasks and not task_lookup_skipped:
                if task_truncated and not tasks:
                    gap_reasons.append("open sales-owned follow-up not verified because task lookup was truncated")
                elif not task_truncated and not tasks:
                    gap_reasons.append("no open sales-owned follow-up found")

            score_input = dict(summary)
            score_input.update(_sales_followup_signals(tasks, task_truncated))
            next_due = score_input.get("next_sales_followup_due_at") or ""
            row = {
                "company_id": company_id,
                "hubspot_scoped": True,
                "scope_source": SCOPE_SOURCE,
                "name": summary.get("name"),
                "country": summary.get("country"),
                "owner_id": summary.get("owner_id"),
                "owner_email": summary.get("owner_email"),
                "owner_name": summary.get("owner_name"),
                "account_status": summary.get("account_status"),
                "account_status_source": summary.get("account_status_source"),
                "contract_end_date": summary.get("contract_end_date"),
                "current_tool_renewal_date": summary.get("current_tool_renewal_date"),
                "current_tools": summary.get("current_tools"),
                "contract_or_renewal_date": primary_renewal["value"],
                "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
                "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
                "days_until_renewal": days_until_renewal,
                "renewal_match_fields": [match["property_name"] for match in renewal_matches],
                "renewal_matches": [
                    {"property_name": match["property_name"], "value": match["value"]}
                    for match in renewal_matches
                ],
                "enrichment_status": summary.get("enrichment_status"),
                "missing_fields": missing,
                "decision_maker_count": summary.get("decision_maker_count"),
                "verified_decision_maker_count": summary.get("verified_decision_maker_count"),
                "buying_role_contact_count": summary.get("buying_role_contact_count"),
                "role_inferred_decision_maker_candidate_count": summary.get(
                    "role_inferred_decision_maker_candidate_count"
                ),
                "decision_maker_coverage": summary.get("decision_maker_coverage"),
                "decision_maker_count_source": summary.get("decision_maker_count_source"),
                "buying_role_contact_count_source": summary.get("buying_role_contact_count_source"),
                "followup_task_lookup_complete": bool(
                    include_followup_tasks and not task_lookup_skipped and not task_truncated
                ),
                "open_followup_task_count": len(tasks),
                "next_sales_followup_due_at": next_due,
                "has_gap": bool(gap_reasons),
                "gap_reasons": gap_reasons,
                **_score_company(score_input),
            }
            renewing_accounts.append(row)
            if gap_reasons:
                gap_accounts.append(row)

        renewing_accounts.sort(
            key=lambda item: (
                0 if item.get("open_followup_task_count") == 0 else 1,
                item.get("days_until_renewal", 999),
                -item.get("priority_score", 0),
            )
        )
        gap_accounts.sort(
            key=lambda item: (
                0 if item.get("open_followup_task_count") == 0 else 1,
                item.get("days_until_renewal", 999),
                -item.get("priority_score", 0),
            )
        )

        missing_renewal_date_accounts = []
        for company in missing_data.get("results", []):
            summary = _summarize_company(company)
            missing_fields = list(summary.get("missing_fields", []))
            if "contract end date" not in missing_fields:
                missing_fields.append("contract end date")
            missing_renewal_date_accounts.append(
                {
                    "company_id": summary.get("company_id"),
                    "hubspot_scoped": True,
                    "scope_source": SCOPE_SOURCE,
                    "name": summary.get("name"),
                    "country": summary.get("country"),
                    "owner_id": summary.get("owner_id"),
                    "owner_email": summary.get("owner_email"),
                    "owner_name": summary.get("owner_name"),
                    "account_status": summary.get("account_status"),
                    "account_status_source": summary.get("account_status_source"),
                    "contract_end_date": summary.get("contract_end_date"),
                    "current_tool_renewal_date": summary.get("current_tool_renewal_date"),
                    "current_tools": summary.get("current_tools"),
                    "renewal_source_of_truth": RENEWAL_SOURCE_OF_TRUTH_PROPERTY,
                    "current_tools_source_of_truth": CURRENT_TOOLS_SOURCE_OF_TRUTH_PROPERTY,
                    "enrichment_status": summary.get("enrichment_status"),
                    "missing_fields": missing_fields,
                    "decision_maker_count": summary.get("decision_maker_count"),
                    "verified_decision_maker_count": summary.get("verified_decision_maker_count"),
                    "buying_role_contact_count": summary.get("buying_role_contact_count"),
                    "decision_maker_coverage": summary.get("decision_maker_coverage"),
                    "classification_needed": "missing_contract_end_date",
                }
            )
        missing_renewal_date_accounts.sort(key=lambda item: (str(item.get("country") or ""), str(item.get("name") or "")))

        metadata = _search_metadata(data)
        missing_metadata = _search_metadata(missing_data)
        source_bits = ["HubSpot company renewal search"]
        if include_missing_renewal_dates:
            source_bits.append("HubSpot missing-contract-end-date search")
        if include_followup_tasks and target_owner_id:
            source_bits.append("batched HubSpot task lookup")
        scope_response = _scope_response(scope, selected, target_owner_id, target_owner_email)
        scope_response["renewal_window_start"] = today.isoformat()
        scope_response["renewal_window_end"] = window_end.isoformat()
        account_truncated = bool(metadata.get("truncated") or missing_metadata.get("truncated"))
        result_truncated = bool(account_truncated or task_truncated)
        caveat = (
            "T-90 search uses HubSpot contract_end_date as renewal source of truth before enrichment checks and separately lists target accounts missing contract_end_date. current_tool_renewal_date is returned as secondary context only. Raw contacts and task bodies are omitted."
        )
        if account_truncated:
            caveat += " Account buckets are truncated; do not present counts as complete."
        if task_truncated:
            caveat += " Task lookup was truncated, so missing-follow-up flags may be incomplete."
        if task_lookup_skipped:
            caveat += " Follow-up task lookup was skipped because no single target owner was selected; no-follow-up gaps were not asserted."
        answer_payload = {
            "known_t90_contract_end_date_accounts": renewing_accounts,
            "renewing_next_90_days": renewing_accounts,
            "gap_accounts": gap_accounts,
            "missing_contract_end_date_accounts": missing_renewal_date_accounts,
            "counts": {
                "renewing_account_count": len(renewing_accounts),
                "gap_count": len(gap_accounts),
                "missing_contact_account_count": len(
                    [row for row in renewing_accounts if "associated contact" in row.get("missing_fields", [])]
                ),
                "missing_decision_maker_account_count": len(
                    [row for row in renewing_accounts if "decision maker" in row.get("missing_fields", [])]
                ),
                "role_only_decision_maker_account_count": len(
                    [
                        row
                        for row in renewing_accounts
                        if row.get("decision_maker_coverage", {}).get("verified_decision_maker_count", 0) < 1
                        and row.get("decision_maker_coverage", {}).get(
                            "role_inferred_decision_maker_candidate_count",
                            0,
                        )
                        > 0
                    ]
                ),
                "missing_contract_end_date_account_count": len(missing_renewal_date_accounts),
                "known_t90_requested_limit": requested_limit,
                "missing_contract_end_date_requested_limit": missing_metadata.get("requested_limit"),
            },
            "required_output_sections": [
                "known_t90_contract_end_date_accounts",
                "missing_contract_end_date_accounts",
                "completeness",
            ],
        }
        return {
            "answer": answer_payload,
            "renewing_next_90_days": renewing_accounts,
            "gap_accounts": gap_accounts,
            "missing_contract_end_date_accounts": missing_renewal_date_accounts,
            "missing_renewal_date_accounts": missing_renewal_date_accounts,
            "required_output_sections": answer_payload["required_output_sections"],
            "data_sources": {
                "source_of_truth": {
                    "target_accounts": "HubSpot companies hs_is_target_account",
                    "ownership": "HubSpot owners API plus company hubspot_owner_id",
                    "country": "HubSpot company company_country",
                    "renewal_timing": "HubSpot company contract_end_date",
                    "current_tools": "HubSpot company current_tools",
                },
                "secondary_context": {
                    "current_tool_renewal_date": "Returned for context only; not used as the T-90 renewal source of truth.",
                    "sales_followup_tasks": "Existing incomplete sales-owned HubSpot tasks when a single owner scope is selected.",
                },
            },
            "source": " plus ".join(source_bits),
            "scope": scope_response,
            **metadata,
            "account_list_complete": not account_truncated,
            "known_t90_account_list_complete": not bool(metadata.get("truncated")),
            "missing_contract_end_date_account_list_complete": not bool(missing_metadata.get("truncated")),
            "renewing_account_count": len(renewing_accounts),
            "gap_count": len(gap_accounts),
            "missing_contract_end_date_account_count": len(missing_renewal_date_accounts),
            "missing_renewal_date_account_count": len(missing_renewal_date_accounts),
            "missing_contract_end_date_metadata": missing_metadata,
            "missing_renewal_date_metadata": missing_metadata,
            "task_lookup": {
                **task_metadata,
                "truncated": task_truncated,
                "skipped": task_lookup_skipped,
            },
            "confidence": "needs-check" if result_truncated or task_lookup_skipped else "verified",
            "caveat": caveat,
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "owner_email": owner_email})


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
                if context is None:
                    raise ScopeError("One or more requested companies are outside caller scope or are not HubSpot target accounts.")
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
def scan_drive_event_photos(
    slack_user_email: str,
    drive_files: list[dict[str, Any]],
    folder_id: str = DRIVE_ALL_RANDOM_FOLDER_ID,
    limit: int = 20,
    event_name: str = "",
    context_text: str = "",
    luma_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Normalize recent Drive all-random photo metadata into photo-match work items."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if not isinstance(drive_files, list):
            return _blocked("Drive file metadata list is required; raw images must stay transient.", _scope_response(scope, list(scope.get("countries", ()))))

        requested_limit = _bounded_int(limit, default=20, maximum=PHOTO_SCAN_LIMIT)
        photos = []
        skipped_non_images = 0
        for raw_file in drive_files[:requested_limit]:
            if not isinstance(raw_file, dict):
                continue
            metadata = {**raw_file, "folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID}
            if not _is_photo_file(metadata):
                skipped_non_images += 1
                continue
            source_pointer = _photo_source_pointer("drive", metadata)
            photo_key = _photo_key(source_pointer)
            luma_event_context = _photo_luma_event_context(source_pointer, luma_events)
            resolved_event_name = event_name or luma_event_context.get("event_name") or ""
            confirmation_request = _photo_confirmation_request(source_pointer, luma_event_context=luma_event_context)
            photos.append(
                {
                    "photo_key": photo_key,
                    "source_pointer": source_pointer,
                    "source_timestamp": source_pointer.get("source_timestamp")
                    or source_pointer.get("created_time")
                    or source_pointer.get("modified_time")
                    or "",
                    "reconcile_keys": {
                        "photo_key": photo_key,
                        "md5_checksum": source_pointer.get("md5_checksum") or "",
                        "filename": source_pointer.get("filename") or "",
                        "source_timestamp": source_pointer.get("source_timestamp") or source_pointer.get("created_time") or "",
                    },
                    "luma_event_context": luma_event_context,
                    "hubspot_custom_object_plan": _photo_custom_object_plan(
                        photo_key,
                        source_pointer,
                        resolved_event_name,
                        context_text,
                        luma_event_context,
                    ),
                    "confirmation_request": confirmation_request,
                    "next_tool": "propose_photo_people_matches",
                }
            )

        confirmation_batches = _photo_confirmation_batches(photos)
        return {
            "answer": {
                "folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID,
                "photos": photos,
                "photo_count": len(photos),
                "skipped_non_image_count": skipped_non_images,
                "luma_event_date_correlation": {
                    "enabled": isinstance(luma_events, list),
                    "candidate_event_count": len(luma_events or []) if isinstance(luma_events, list) else 0,
                    "auto_event_tag_only": True,
                    "person_auto_tag": False,
                },
                "confirmation_policy": "Ask the Slack uploader to identify or confirm every matched person before any HubSpot association.",
                "uploader_confirmation_batches": confirmation_batches,
                "will_mutate_hubspot": False,
                "raw_image_copy": False,
                "daily_pilot_scan_ready": True,
            },
            "source": "Google Drive all-random folder metadata plus HubSpot caller scope",
            "scope": {
                **_scope_response(scope, list(scope.get("countries", ()))),
                "drive_folder_id": folder_id or DRIVE_ALL_RANDOM_FOLDER_ID,
            },
            "total": len(drive_files),
            "requested_limit": requested_limit,
            "returned_count": len(photos),
            "has_more": len(drive_files) > requested_limit,
            "truncated": len(drive_files) > requested_limit,
            "confidence": "needs-check",
            "caveat": (
                "Metadata intake only. The Drive runtime must download images transiently for vision/OCR, then pass clues into propose_photo_people_matches. "
                "HubSpot custom object writes are represented as a preview plan; raw image copies are not stored by default."
            ),
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


@mcp.tool()
def propose_photo_people_matches(
    slack_user_email: str,
    photo_source: str,
    photo_metadata: dict[str, Any],
    context_text: str = "",
    vision_clues: dict[str, Any] | None = None,
    explicit_contact_name: str = "",
    explicit_company_name: str = "",
    event_name: str = "",
    country: str = "",
    limit: int = PHOTO_MATCH_LIMIT,
    luma_event_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Propose HubSpot contact/company matches for one Slack or Drive event photo."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        source = _photo_source_type(photo_source)
        if not source:
            return _blocked("photo_source must be either drive or slack.", _scope_response(scope, list(scope.get("countries", ()))))
        if not isinstance(photo_metadata, dict):
            return _blocked("photo_metadata must include source pointers, not raw image bytes.", _scope_response(scope, list(scope.get("countries", ()))))

        source_pointer = _photo_source_pointer(source, photo_metadata)
        photo_key = _photo_key(source_pointer)
        metadata_events = photo_metadata.get("luma_event_candidates") or photo_metadata.get("luma_events") or luma_event_candidates
        luma_event_context = _photo_luma_event_context(source_pointer, metadata_events)
        resolved_event_name = event_name or luma_event_context.get("event_name") or ""
        resolved_country = country or luma_event_context.get("country") or ""
        hints = _photo_matching_hints(
            context_text,
            vision_clues,
            explicit_contact_name,
            explicit_company_name,
            resolved_event_name,
            resolved_country,
            luma_event_context,
        )
        selected_countries = _photo_scope_countries(scope, hints)
        if hints.get("countries") and not selected_countries:
            return _blocked("Requested photo country is outside caller scope.", _scope_response(scope, []))

        requested_limit = _bounded_int(limit, default=PHOTO_MATCH_LIMIT, maximum=10)
        company_candidates = _photo_company_candidates(scope, hints, requested_limit)
        contact_candidates = _photo_contact_candidates(scope, hints, company_candidates, requested_limit)
        prompt = _photo_missing_clue_prompt(hints, contact_candidates, company_candidates)
        confirmation_request = _photo_confirmation_request(
            source_pointer,
            prompt,
            has_candidates=bool(contact_candidates or company_candidates),
            luma_event_context=luma_event_context,
        )

        return {
            "answer": {
                "photo_key": photo_key,
                "source_pointer": source_pointer,
                "luma_event_context": luma_event_context,
                "hints": hints,
                "contact_candidates": contact_candidates,
                "company_candidates": company_candidates,
                "missing_clue_prompt": prompt,
                "confirmation_request": confirmation_request,
                "requires_human_confirmation": True,
                "will_mutate_hubspot": False,
                "raw_image_copy": False,
                "hubspot_custom_object_plan": _photo_custom_object_plan(
                    photo_key,
                    source_pointer,
                    resolved_event_name,
                    context_text,
                    luma_event_context,
                ),
                "next_step": "Ask the original uploader to confirm one contact/company before preparing the HubSpot note and WhatsApp follow-up task.",
            },
            "source": "Slack/Drive photo source pointer, transient LLM vision clues, and HubSpot scoped contact/company search",
            "scope": {
                **_scope_response(scope, selected_countries or list(scope.get("countries", ()))),
                "photo_source": source,
            },
            "total": len(contact_candidates),
            "requested_limit": requested_limit,
            "returned_count": len(contact_candidates),
            "has_more": False,
            "truncated": False,
            "confidence": "needs-check",
            "caveat": "Photo matching is proposal-only. Even high-confidence matches require human confirmation before CRM association or follow-up task preview.",
        }
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "photo_source": photo_source})


@mcp.tool()
def plan_event_photo_followup(
    slack_user_email: str,
    selected_match: dict[str, Any],
    event_name: str = "",
    due_at: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Preview the HubSpot note and WhatsApp follow-up task after a human confirms a photo match."""

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] == "manager":
            return _blocked("Managers have read-only team scope and cannot create photo follow-up write-back previews.", _scope_response(scope, list(scope.get("countries", ()))))
        if not isinstance(selected_match, dict):
            return _blocked("selected_match must be the confirmed contact/company candidate.", _scope_response(scope, list(scope.get("countries", ()))))

        contact_id = str(selected_match.get("contact_id") or "").strip()
        company_id = _selected_match_company_id(selected_match)
        if not contact_id or not company_id:
            return _blocked("Confirmed photo match requires contact_id and scoped company_id.", _scope_response(scope, list(scope.get("countries", ()))))

        company = _assert_company_access(company_id, scope)
        company_name = _selected_match_company_name(selected_match, company)
        contact_name = str(selected_match.get("display_name") or selected_match.get("contact_name") or "there")
        due = due_at or _next_business_day_10_sg()
        draft = _photo_followup_draft(contact_name, company_name, event_name)
        source_pointer = selected_match.get("source_pointer") or selected_match.get("photo_source_pointer") or {}
        if not isinstance(source_pointer, dict):
            source_pointer = {}
        photo_key = str(selected_match.get("photo_key") or (_photo_key(source_pointer) if source_pointer else ""))
        note_summary = _short_text(
            f"Event photo match confirmed for {contact_name} from {company_name}"
            + (f" after {event_name}" if event_name else "")
            + ". Prepare manual WhatsApp follow-up; no message was sent.",
            500,
        )
        action = {
            "company_id": company_id,
            "contact_id": contact_id,
            "task": f"WhatsApp follow-up after {event_name or 'event photo'}",
            "note_summary": note_summary,
            "due_at": due,
            "draft_whatsapp_copy": draft,
            "source_type": "event_photo",
            "source_url": source_pointer.get("permalink") or source_pointer.get("drive_link") or "",
            "source_evidence": {
                "photo_key": photo_key,
                "source_pointer": source_pointer,
                "match_evidence": selected_match.get("evidence", []),
                "confidence_band": selected_match.get("confidence_band", "needs-check"),
            },
            "confidence": "needs-check",
            "selected": True,
        }
        writeback = plan_hubspot_writeback(slack_user_email, [action], approval_marker)
        if writeback.get("confidence") == "blocked":
            return writeback
        preview_id = writeback.get("answer", {}).get("preview_id", "")
        return {
            "answer": {
                "preview_id": preview_id,
                "company_id": company_id,
                "contact_id": contact_id,
                "hubspot_note_summary": note_summary,
                "whatsapp_followup_task": {
                    "subject": action["task"],
                    "due_at": due,
                    "type": "TODO",
                    "company_id": company_id,
                    "contact_id": contact_id,
                },
                "draft_whatsapp_copy": draft,
                "selected_actions": writeback.get("answer", {}).get("actions", [action]),
                "custom_object_preview": {
                    "nurture_event": {"event_name": event_name or "event photo"},
                    "nurture_event_photo": {"photo_key": photo_key, "source_pointer": source_pointer, "raw_image_copy": False},
                    "nurture_person_appearance": {
                        "contact_id": contact_id,
                        "company_id": company_id,
                        "confirmed_by": scope.get("email"),
                        "confirmation_required": False,
                    },
                },
                "requires_approval": True,
                "will_mutate_hubspot": False,
                "whatsapp_auto_send": False,
            },
            "source": "Confirmed photo match plus NurtureAny HubSpot write-back dry run",
            "scope": _scope_response(scope, [company.get("properties", {}).get("company_country") or ""]),
            "confidence": "verified",
            "caveat": "Preview only. Create the HubSpot note/task only after explicit approval; WhatsApp is draft-only and never auto-sent in V1.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


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

    try:
        scope = _caller_scope(slack_user_email)
        if scope["kind"] == "blocked":
            return _blocked("Caller identity is not mapped to an allowed scope.", {"caller_email": slack_user_email})
        if scope["kind"] == "manager":
            return _blocked("Managers have read-only team scope and cannot create HubSpot write-back previews.", _scope_response(scope, list(scope.get("countries", ()))))
        if not selected_actions:
            return _blocked("At least one selected action is required for a write-back preview.", _scope_response(scope, list(scope.get("countries", ()))))

        scoped_actions = selected_actions[:50]
        for action in scoped_actions:
            company_id = str(action.get("company_id") or "").strip()
            if not company_id:
                raise ScopeError("Every write-back preview action requires a scoped HubSpot company_id.")
            _assert_company_access(company_id, scope)

        payload = json.dumps(
            {
                "caller": scope.get("email"),
                "actions": scoped_actions,
                "approval_marker": approval_marker,
                "date": datetime.now(timezone.utc).isoformat(),
            },
            sort_keys=True,
        )
        preview_id = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
        preview = []
        for action in scoped_actions:
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
            "caveat": "Preview only. Managers are read-only, and mutation tools are disabled in V1 until explicit write phase approval.",
        }
    except ScopeError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})
    except HubSpotError as error:
        return _blocked(str(error), {"caller_email": slack_user_email})


if __name__ == "__main__":
    mcp.run("stdio")
