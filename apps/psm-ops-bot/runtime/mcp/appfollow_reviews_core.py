#!/usr/bin/env python3
"""AppFollow review helpers for PSM Ops Bot.

This module is shared by the MCP adapter and the no-agent Slack triage
script so the API contract, Slack parser, and idempotency key stay identical.
"""

from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any


APPFOLLOW_API_BASE_URL = "https://api.appfollow.io/api/v2"
APPFOLLOW_USER_AGENT = "StaffAny-PSMOps/1.0 (+https://staffany.com)"
APPFOLLOW_TIMEOUT_SECONDS = 20
DEFAULT_REVIEW_LOOKBACK_DAYS = 30
DEFAULT_STATE_PATH = "~/.hermes/profiles/psmopsbot/state/appfollow_reviews.json"
APPFOLLOW_STATE_KEY_DESCRIPTION = "store + ext_id + review_id"
MAX_REPLY_CHARS = 350
APPFOLLOW_REVIEW_SOURCE = "AppFollow API"
STAFFANY_SUPPORT_EMAIL = "support@staffany.com"
IDENTITY_TAG_UNKNOWN = "identity_unknown"
IDENTITY_TAG_REQUESTED_PRIVATE = "identity_requested_private"
IDENTITY_TAG_CANDIDATE = "identity_candidate"
IDENTITY_TAG_CONFIRMED = "identity_confirmed"


class AppFollowError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def truthy(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _api_base_url() -> str:
    return _env("APPFOLLOW_API_BASE_URL", APPFOLLOW_API_BASE_URL).rstrip("/")


def _api_token() -> str:
    token = _env("APPFOLLOW_API_TOKEN")
    if not token:
        raise AppFollowError("APPFOLLOW_API_TOKEN is not configured.")
    return token


def _safe_detail(value: Any, limit: int = 400) -> str:
    text = "" if value is None else str(value)
    token = _env("APPFOLLOW_API_TOKEN")
    if token:
        text = text.replace(token, "[redacted]")
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[redacted]", text)
    return text[:limit]


def request_json(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> Any:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in {None, ""}})
    url = f"{_api_base_url()}{path}"
    if query:
        url = f"{url}?{query}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "accept": "application/json",
            "content-type": "application/json; charset=utf-8",
            "user-agent": APPFOLLOW_USER_AGENT,
            "X-AppFollow-API-Token": _api_token(),
        },
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=APPFOLLOW_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            if not raw:
                return {}
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type or raw[:1] in {"{", "["}:
                return json.loads(raw)
            return {"status": "ok", "data": raw}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise AppFollowError(f"AppFollow API failed: HTTP {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise AppFollowError(f"AppFollow API request timed out or failed: {_safe_detail(reason)}") from error


def blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": APPFOLLOW_REVIEW_SOURCE,
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def tool_result(
    answer: Any,
    scope: dict[str, Any],
    *,
    confidence: str = "needs-check",
    caveat: str = "AppFollow is review metadata/reply/tag truth. Slack remains the triage surface.",
) -> dict[str, Any]:
    return {
        "answer": answer,
        "source": APPFOLLOW_REVIEW_SOURCE,
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


def list_appfollow_apps() -> dict[str, Any]:
    scope = {"endpoint": "GET /account/apps", "credit_policy": "1 credit per request"}
    try:
        payload = request_json("GET", "/account/apps")
    except AppFollowError as error:
        return blocked(str(error), scope)
    return tool_result(payload, scope, confidence="verified")


def _default_review_window() -> tuple[str, str]:
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=DEFAULT_REVIEW_LOOKBACK_DAYS)
    return start.isoformat(), today.isoformat()


def _review_params(
    *,
    ext_id: str = "",
    collection_name: str = "",
    review_id: str = "",
    country: str = "",
    lang: str = "",
    from_date: str = "",
    to_date: str = "",
    last_modified: str = "",
    page: int = 1,
) -> dict[str, Any]:
    start, end = _default_review_window()
    params: dict[str, Any] = {
        "ext_id": ext_id,
        "collection_name": collection_name,
        "country": country,
        "lang": lang,
        "review_id": review_id,
        "from": from_date or start,
        "to": to_date or end,
        "page": max(1, int(page or 1)),
    }
    if last_modified:
        params["last_modified"] = last_modified
    return {key: value for key, value in params.items() if value not in {None, ""}}


def get_appfollow_review(
    *,
    ext_id: str = "",
    collection_name: str = "",
    review_id: str = "",
    country: str = "",
    lang: str = "",
    from_date: str = "",
    to_date: str = "",
    last_modified: str = "",
    page: int = 1,
) -> dict[str, Any]:
    params = _review_params(
        ext_id=ext_id,
        collection_name=collection_name,
        review_id=review_id,
        country=country,
        lang=lang,
        from_date=from_date,
        to_date=to_date,
        last_modified=last_modified,
        page=page,
    )
    scope = {
        "endpoint": "GET /reviews",
        "params": {key: value for key, value in params.items() if key != "review_id" or value},
        "credit_policy": "10 credits per request; use only when a Slack alert or human action points to a review.",
    }
    if not params.get("ext_id") and not params.get("collection_name"):
        return blocked("ext_id or collection_name is required before fetching AppFollow reviews.", scope)
    try:
        payload = request_json("GET", "/reviews", params=params)
    except AppFollowError as error:
        return blocked(str(error), scope)
    return tool_result(payload, scope, confidence="verified")


def _tags_csv(tags: str | list[str]) -> str:
    raw_tags = tags if isinstance(tags, list) else str(tags or "").split(",")
    cleaned: list[str] = []
    seen: set[str] = set()
    for tag in raw_tags:
        value = re.sub(r"\s+", " ", str(tag or "")).strip()
        if not value:
            continue
        key = value.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(value)
    return ",".join(cleaned)


def tag_appfollow_review(
    *,
    ext_id: str,
    review_id: str,
    tags: str | list[str],
    apps_id: int | str | None = None,
    apply: bool = False,
) -> dict[str, Any]:
    body = {
        "ext_id": str(ext_id or "").strip(),
        "review_id": str(review_id or "").strip(),
        "tags": _tags_csv(tags),
    }
    if apps_id not in {None, ""}:
        body["apps_id"] = int(apps_id)
    scope = {
        "endpoint": "POST /reviews/tags",
        "review_id": body["review_id"],
        "ext_id": body["ext_id"],
        "tags": body["tags"],
        "apply": bool(apply),
        "credit_policy": "10 credits per request; harmless internal tag first.",
    }
    if not body["ext_id"] or not body["review_id"] or not body["tags"]:
        return blocked("ext_id, review_id, and tags are required before updating AppFollow tags.", scope)
    if not apply:
        return tool_result(
            {"status": "preview", "would_post": body},
            scope,
            confidence="preview",
            caveat="Dry run only. Pass apply=true only for a harmless internal tag smoke first.",
        )
    try:
        payload = request_json("POST", "/reviews/tags", body=body)
    except AppFollowError as error:
        return blocked(str(error), scope)
    return tool_result(payload, scope, confidence="verified")


def _review_text_from_payload(review: dict[str, Any]) -> str:
    candidates = [
        review.get("text"),
        review.get("body"),
        review.get("content"),
        review.get("review"),
        review.get("title"),
    ]
    return " ".join(str(value or "") for value in candidates if str(value or "").strip()).strip()


def _shorten(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


def _normalize_email(value: str) -> str:
    return re.sub(r"\s+", "", value or "").strip().lower()


def _normalize_phone(value: str) -> str:
    return re.sub(r"\D+", "", value or "")


def _redact_email(value: str) -> str:
    email = _normalize_email(value)
    if "@" not in email:
        return ""
    local, domain = email.split("@", 1)
    if not local or not domain:
        return "[redacted-email]"
    if len(local) <= 2:
        return f"{local[0]}***@{domain}"
    return f"{local[:2]}***@{domain}"


def _redact_phone(value: str) -> str:
    digits = _normalize_phone(value)
    if not digits:
        return ""
    tail = digits[-4:] if len(digits) >= 4 else digits
    return f"[redacted-phone:{tail}]"


def _redact_private_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", lambda match: _redact_email(match.group(0)), text)
    text = re.sub(r"(?:\+?\d[\d\s().-]{6,}\d)", lambda match: _redact_phone(match.group(0)), text)
    return text


def _review_key_from_inputs(
    review: dict[str, Any] | None = None,
    *,
    review_key: str = "",
    store: str = "",
    ext_id: str = "",
    review_id: str = "",
) -> str:
    if review_key:
        return str(review_key).strip()
    payload = {
        "store": store,
        "ext_id": ext_id,
        "review_id": review_id,
        **(review or {}),
    }
    return review_state_key(payload)


def _public_private_contact_cta() -> str:
    return (
        f"Please email {STAFFANY_SUPPORT_EMAIL} with your StaffAny account email or phone number, "
        "plus your company/outlet, so we can follow up privately."
    )


def draft_appfollow_reply(review: dict[str, Any] | None = None, issue_summary: str = "") -> dict[str, Any]:
    review = review or {}
    text = _review_text_from_payload(review)
    title = str(review.get("title") or "").strip()
    theme = classify_appfollow_review(review).get("theme") or "app experience"
    issue = _shorten(issue_summary or title or text or f"{theme} issue", 90)
    reply = (
        "Thanks for flagging this. We are checking the issue on our side"
        f" ({issue}). {_public_private_contact_cta()}"
    )
    if len(reply) > MAX_REPLY_CHARS:
        reply = _shorten(reply, MAX_REPLY_CHARS)
    scope = {
        "review_id": str(review.get("review_id") or review.get("id") or "").strip(),
        "theme": theme,
        "requires_approval": True,
        "approval_phrase": "post reply",
        "support_email": STAFFANY_SUPPORT_EMAIL,
    }
    return tool_result(
        {"status": "draft", "answer_text": reply, "support_email": STAFFANY_SUPPORT_EMAIL},
        scope,
        confidence="draft",
        caveat=(
            "Draft only. Public App Store / Play Store replies require same-thread approval: post reply. "
            "Never ask the reviewer to post email or phone in the public review."
        ),
    )


def _walk_values(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            values.extend(_walk_values(child))
    elif isinstance(value, list):
        for child in value:
            values.extend(_walk_values(child))
    elif value not in {None, ""}:
        values.append(str(value))
    return values


def _extract_emails(value: Any) -> set[str]:
    emails: set[str] = set()
    for text in _walk_values(value):
        for match in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text):
            emails.add(_normalize_email(match))
    return emails


def _extract_phone_digits(value: Any) -> set[str]:
    phones: set[str] = set()
    for text in _walk_values(value):
        for match in re.findall(r"(?:\+?\d[\d\s().-]{6,}\d)", text):
            digits = _normalize_phone(match)
            if len(digits) >= 7:
                phones.add(digits)
    return phones


def _safe_c360_group_summary(group: Any) -> dict[str, Any]:
    if not isinstance(group, dict):
        return {"raw_type": type(group).__name__}
    safe: dict[str, Any] = {}
    for source_key, output_key in [
        ("customerKey", "customer_key"),
        ("customer_key", "customer_key"),
        ("routeKey", "route_key"),
        ("route_key", "route_key"),
        ("hubspotCompanyId", "hubspot_company_id"),
        ("companyName", "company_name"),
        ("customerName", "customer_name"),
        ("displayName", "display_name"),
        ("name", "name"),
    ]:
        if group.get(source_key) not in {None, ""} and output_key not in safe:
            safe[output_key] = group.get(source_key)
    org_matches = group.get("orgMatches")
    if isinstance(org_matches, list):
        safe["org_match_count"] = len(org_matches)
    matched_fields = group.get("matchedFields")
    if isinstance(matched_fields, list):
        safe["matched_fields"] = matched_fields[:8]
    return safe


def _c360_search_by_company(company_or_outlet: str, slack_thread_url: str = "") -> dict[str, Any]:
    try:
        from psm_c360_server import search_c360_customers  # type: ignore
    except Exception as error:
        return {
            "status": "blocked",
            "message": f"Customer 360 search adapter unavailable: {error.__class__.__name__}",
            "answer": [],
        }
    return search_c360_customers(company_or_outlet, limit=5, slack_thread_url=slack_thread_url)


def _private_claim_from_inputs(
    private_claim: dict[str, Any] | None,
    *,
    email: str = "",
    phone: str = "",
    company_or_outlet: str = "",
    reviewer_nickname: str = "",
    review_text: str = "",
) -> dict[str, str]:
    claim = private_claim or {}
    return {
        "email": str(email or claim.get("email") or claim.get("account_email") or "").strip(),
        "phone": str(phone or claim.get("phone") or claim.get("account_phone") or "").strip(),
        "company_or_outlet": str(
            company_or_outlet
            or claim.get("company_or_outlet")
            or claim.get("company")
            or claim.get("outlet")
            or ""
        ).strip(),
        "reviewer_nickname": str(reviewer_nickname or claim.get("reviewer_nickname") or claim.get("reviewer") or "").strip(),
        "review_text": str(review_text or claim.get("review_text") or claim.get("text") or "").strip(),
    }


def suggest_appfollow_review_identity_candidates(
    *,
    review: dict[str, Any] | None = None,
    private_claim: dict[str, Any] | None = None,
    c360_candidates: list[Any] | None = None,
    email: str = "",
    phone: str = "",
    company_or_outlet: str = "",
    reviewer_nickname: str = "",
    review_text: str = "",
    slack_thread_url: str = "",
    state_path: str = "",
) -> dict[str, Any]:
    """Suggest private-claim identity candidates without exposing raw PII."""

    review = review or {}
    claim = _private_claim_from_inputs(
        private_claim,
        email=email,
        phone=phone,
        company_or_outlet=company_or_outlet,
        reviewer_nickname=reviewer_nickname,
        review_text=review_text,
    )
    normalized_email = _normalize_email(claim["email"])
    normalized_phone = _normalize_phone(claim["phone"])
    review_key = _review_key_from_inputs(review)
    signals = {
        "email": bool(normalized_email),
        "phone": bool(normalized_phone),
        "company_or_outlet": bool(claim["company_or_outlet"]),
        "reviewer_nickname": bool(claim["reviewer_nickname"]),
        "review_text": bool(claim["review_text"] or _review_text_from_payload(review)),
    }
    scope = {
        "review_key": review_key,
        "review_id": str(review.get("review_id") or review.get("id") or "").strip(),
        "state_key": APPFOLLOW_STATE_KEY_DESCRIPTION,
        "signals": signals,
        "slack_thread_url": slack_thread_url,
    }
    if not any([normalized_email, normalized_phone, claim["company_or_outlet"]]):
        return tool_result(
            {
                "status": "unknown",
                "review_key": review_key,
                "candidates": [],
                "suggested_tags": [IDENTITY_TAG_UNKNOWN, IDENTITY_TAG_REQUESTED_PRIVATE],
                "public_reply_cta": _public_private_contact_cta(),
                "next_action": "Ask the reviewer to email support@staffany.com with their StaffAny account email or phone number plus company/outlet.",
            },
            scope,
            confidence="needs-check",
            caveat="Reviewer nickname/review text alone is not enough to identify a StaffAny customer or contact.",
        )

    c360_status = "not_run"
    groups: list[Any] = list(c360_candidates or [])
    if not groups and claim["company_or_outlet"]:
        c360_result = _c360_search_by_company(claim["company_or_outlet"], slack_thread_url=slack_thread_url)
        c360_status = str(c360_result.get("confidence") or c360_result.get("status") or "unknown")
        answer = c360_result.get("answer")
        if isinstance(answer, list):
            groups = answer
        elif isinstance(answer, dict):
            groups = [answer]
    elif groups:
        c360_status = "provided"

    candidates: list[dict[str, Any]] = []
    seen_candidates: set[str] = set()

    for group in groups:
        group_emails = _extract_emails(group)
        group_phones = _extract_phone_digits(group)
        group_summary = _safe_c360_group_summary(group)
        key_seed = json.dumps(group_summary, sort_keys=True, default=str)
        if normalized_email and normalized_email in group_emails:
            candidate = {
                "match_type": "exact_email",
                "confidence": "verified",
                "source": "Customer 360 candidate evidence",
                "customer": group_summary,
                "contact": {"email": _redact_email(normalized_email)},
                "reason": "Private support email exactly matches Customer 360/HubSpot candidate evidence.",
            }
            key = f"email:{normalized_email}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(candidate)
        if normalized_phone and normalized_phone in group_phones:
            candidate = {
                "match_type": "phone",
                "confidence": "needs-check",
                "source": "Customer 360 candidate evidence",
                "customer": group_summary,
                "contact": {"phone": _redact_phone(normalized_phone)},
                "reason": "Phone appears in Customer 360 candidate evidence, but phone-only linkage is ambiguous until human-confirmed.",
            }
            key = f"phone:{normalized_phone}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(candidate)
        if claim["company_or_outlet"]:
            candidate = {
                "match_type": "company_or_outlet",
                "confidence": "needs-check",
                "source": "Customer 360 /api/companies",
                "customer": group_summary,
                "contact": {
                    "email": _redact_email(normalized_email) if normalized_email else "",
                    "phone": _redact_phone(normalized_phone) if normalized_phone else "",
                },
                "reason": "Company/outlet from the private support follow-up matched a Customer 360 customer candidate.",
            }
            key = f"company:{claim['company_or_outlet'].lower()}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(candidate)

    if not candidates:
        if normalized_email:
            candidates.append(
                {
                    "match_type": "private_email_claim",
                    "confidence": "needs-check",
                    "source": "private support follow-up",
                    "customer": {},
                    "contact": {"email": _redact_email(normalized_email)},
                    "reason": "Email was provided privately, but no Customer 360/HubSpot candidate evidence matched it yet.",
                }
            )
        if normalized_phone:
            candidates.append(
                {
                    "match_type": "private_phone_claim",
                    "confidence": "needs-check",
                    "source": "private support follow-up",
                    "customer": {},
                    "contact": {"phone": _redact_phone(normalized_phone)},
                    "reason": "Phone was provided privately, but phone-only linkage is ambiguous until human-confirmed.",
                }
            )
        if claim["company_or_outlet"]:
            candidates.append(
                {
                    "match_type": "company_or_outlet_claim",
                    "confidence": "needs-check",
                    "source": "private support follow-up",
                    "customer": {"company_or_outlet": _redact_private_text(claim["company_or_outlet"])},
                    "contact": {},
                    "reason": "Company/outlet was provided privately, but Customer 360 did not return a verified candidate.",
                }
            )

    status = "verified" if any(candidate.get("confidence") == "verified" for candidate in candidates) else "candidate"
    suggested_tags = [IDENTITY_TAG_CANDIDATE]
    return tool_result(
        {
            "status": status,
            "review_key": review_key,
            "c360_status": c360_status,
            "candidates": candidates,
            "suggested_tags": suggested_tags,
            "confirmation_tool": "confirm_appfollow_review_identity",
            "public_reply_cta": _public_private_contact_cta(),
            "private_claim_redacted": {
                "email": _redact_email(normalized_email) if normalized_email else "",
                "phone": _redact_phone(normalized_phone) if normalized_phone else "",
                "company_or_outlet": _redact_private_text(claim["company_or_outlet"]),
                "reviewer_nickname": _redact_private_text(claim["reviewer_nickname"]),
            },
        },
        scope,
        confidence="verified" if status == "verified" else "needs-check",
        caveat="Exact email match can be verified. Phone-only or company/outlet-only candidates need human confirmation.",
    )


def confirm_appfollow_review_identity(
    *,
    review: dict[str, Any] | None = None,
    review_key: str = "",
    store: str = "",
    ext_id: str = "",
    review_id: str = "",
    customer_key: str = "",
    customer_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    confirmation_text: str = "",
    confirmed_by: str = "",
    state_path: str = "",
) -> dict[str, Any]:
    key = _review_key_from_inputs(
        review or {},
        review_key=review_key,
        store=store,
        ext_id=ext_id,
        review_id=review_id,
    )
    scope = {
        "review_key": key,
        "state_key": APPFOLLOW_STATE_KEY_DESCRIPTION,
        "customer_key": customer_key,
        "customer_name": customer_name,
    }
    if not key or key.endswith(":unknown-review"):
        return blocked("review_id or review_key is required before confirming reviewer identity.", scope)
    if not (customer_key or customer_name):
        return blocked("customer_key or customer_name is required before confirming reviewer identity.", scope)
    if not confirmation_text.strip():
        return blocked("confirmation_text is required so the human approval evidence is recorded.", scope)

    confirmation = {
        "status": IDENTITY_TAG_CONFIRMED,
        "review_key": key,
        "customer_key": str(customer_key or "").strip(),
        "customer_name": str(customer_name or "").strip(),
        "contact_email": _redact_email(contact_email),
        "contact_phone": _redact_phone(contact_phone),
        "confirmed_by": _redact_private_text(confirmed_by),
        "confirmation_text": _redact_private_text(confirmation_text),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
    state = load_state(state_path)
    identities = state.setdefault("identity_confirmations", {})
    identities[key] = confirmation
    review_entry = (state.setdefault("reviews", {})).setdefault(key, {})
    review_entry["identity_status"] = IDENTITY_TAG_CONFIRMED
    review_entry["identity_confirmed_at"] = confirmation["confirmed_at"]
    save_state(state, state_path)
    return tool_result(
        {"status": IDENTITY_TAG_CONFIRMED, "review_key": key, "confirmation": confirmation, "suggested_tags": [IDENTITY_TAG_CONFIRMED]},
        scope,
        confidence="verified",
        caveat="Stored only the human-confirmed mapping and redacted contact hints in runtime state outside git.",
    )


def _approval_allows_publish(approval_text: str) -> bool:
    normalized = re.sub(r"\s+", " ", approval_text or "").strip().lower()
    return bool(re.search(r"\b(post|publish)\s+reply\b", normalized))


def publish_appfollow_reply_after_approval(
    *,
    ext_id: str,
    review_id: str,
    answer_text: str,
    approval_text: str,
    login: str = "",
) -> dict[str, Any]:
    body = {
        "ext_id": str(ext_id or "").strip(),
        "review_id": str(review_id or "").strip(),
        "answer_text": _shorten(str(answer_text or ""), 2000),
    }
    if login:
        body["login"] = login.strip()
    scope = {
        "endpoint": "POST /reviews/reply",
        "review_id": body["review_id"],
        "ext_id": body["ext_id"],
        "approval_required": "same-thread approval like: post reply",
        "credit_policy": "10 credits per request; disabled until one approved smoke test.",
    }
    if not body["ext_id"] or not body["review_id"] or not body["answer_text"]:
        return blocked("ext_id, review_id, and answer_text are required before publishing an AppFollow reply.", scope)
    if not _approval_allows_publish(approval_text):
        return blocked("Public reply blocked until same-thread approval includes `post reply` or `publish reply`.", scope)
    if not truthy(_env("PSM_OPS_APPFOLLOW_REPLY_PUBLISH_ENABLED"), default=False):
        return blocked("Public reply publishing is disabled until the approved AppFollow smoke test is complete.", scope)
    try:
        payload = request_json("POST", "/reviews/reply", body=body)
    except AppFollowError as error:
        return blocked(str(error), scope)
    return tool_result(payload, scope, confidence="verified")


def _walk_strings(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, str):
        strings.append(value)
    elif isinstance(value, dict):
        for child in value.values():
            strings.extend(_walk_strings(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_walk_strings(child))
    return strings


def _strip_slack_markup(text: str) -> str:
    value = re.sub(r"<([^>|]+)\|([^>]+)>", r"\2", text or "")
    value = re.sub(r"<([^>]+)>", r"\1", value)
    value = value.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return re.sub(r"\s+", " ", value).strip()


def _extract_first(patterns: list[str], haystack: str, flags: int = re.IGNORECASE) -> str:
    for pattern in patterns:
        match = re.search(pattern, haystack, flags=flags)
        if match:
            return _strip_slack_markup(match.group(1))
    return ""


def _extract_rating(haystack: str) -> int | None:
    star_tokens = re.findall(r":star:|★|⭐", haystack, flags=re.IGNORECASE)
    if star_tokens:
        return len(star_tokens)
    numeric = _extract_first([r"(?:rating|stars?)\D{0,12}([1-5])(?:\s*/\s*5|\s+stars?)?"], haystack)
    if numeric:
        return int(numeric)
    return None


def _extract_appfollow_url(strings: list[str]) -> str:
    for text in strings:
        match = re.search(r"https?://[^\s<>]*appfollow\.io[^\s<>)]*", text)
        if match:
            return match.group(0)
    return ""


def _extract_app_name(plain: str) -> str:
    for pattern in [
        r"\b(?:App Store|Google Play)\s+review\s+for\s+([A-Za-z][A-Za-z0-9 '&().-]{2,80})",
        r"\b(?:app|application)\D{0,8}([A-Za-z][A-Za-z0-9 '&().-]{2,80})",
    ]:
        match = re.search(pattern, plain, flags=re.IGNORECASE)
        if match:
            value = _strip_slack_markup(match.group(1))
            if value.lower() not in {"app store", "google play"}:
                return value
    return ""


def _review_id_from_strings(strings: list[str]) -> str:
    haystack = "\n".join(strings)
    return _extract_first(
        [
            r"[?&]review_id=([A-Za-z0-9_-]+)",
            r"\breview[_\s-]*id\D{0,12}([A-Za-z0-9_-]+)",
            r"/reviews/([A-Za-z0-9_-]+)",
        ],
        haystack,
    )


def _apps_id_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url or "")
    match = re.search(r"/reviews/(\d+)", parsed.path)
    return match.group(1) if match else ""


def _resolve_ext_id(app_name: str = "", store: str = "", apps_id: str = "") -> str:
    explicit = _env("APPFOLLOW_DEFAULT_EXT_ID") or _env("PSM_OPS_APPFOLLOW_DEFAULT_EXT_ID")
    if explicit:
        return explicit
    raw_mapping = _env("PSM_OPS_APPFOLLOW_APP_EXT_IDS")
    if not raw_mapping:
        return ""
    try:
        mapping = json.loads(raw_mapping)
    except json.JSONDecodeError:
        return ""
    if not isinstance(mapping, dict):
        return ""
    candidates = [
        f"{store}:{app_name}".lower(),
        app_name.lower(),
        apps_id,
        store.lower(),
    ]
    normalized = {str(key).strip().lower(): str(value).strip() for key, value in mapping.items()}
    for candidate in candidates:
        if candidate and normalized.get(candidate):
            return normalized[candidate]
    return ""


def _resolve_collection_name(app_name: str = "", store: str = "", apps_id: str = "") -> str:
    explicit = _env("APPFOLLOW_DEFAULT_COLLECTION_NAME") or _env("PSM_OPS_APPFOLLOW_DEFAULT_COLLECTION_NAME")
    if explicit:
        return explicit
    raw_mapping = _env("PSM_OPS_APPFOLLOW_COLLECTION_NAMES")
    if not raw_mapping:
        return ""
    try:
        mapping = json.loads(raw_mapping)
    except json.JSONDecodeError:
        return ""
    if not isinstance(mapping, dict):
        return ""
    candidates = [
        f"{store}:{app_name}".lower(),
        app_name.lower(),
        apps_id,
        store.lower(),
    ]
    normalized = {str(key).strip().lower(): str(value).strip() for key, value in mapping.items()}
    for candidate in candidates:
        if candidate and normalized.get(candidate):
            return normalized[candidate]
    return ""


def extract_appfollow_review_from_slack_message(message: dict[str, Any]) -> dict[str, Any]:
    strings = _walk_strings(message)
    haystack = "\n".join(strings)
    plain = _strip_slack_markup(haystack)
    review_url = _extract_appfollow_url(strings)
    app_name = _extract_app_name(plain)
    title = _extract_first(
        [
            r"\btitle\D{0,8}([^\n|]+)",
            r"\*([^*\n]{4,120})\*",
            r"“([^”]{4,120})”",
            r"\"([^\"]{4,120})\"",
        ],
        haystack,
    )
    body = _extract_first([r"\b(?:review|body|text|message)\D{0,8}(.{8,500})"], plain, flags=re.IGNORECASE | re.DOTALL)
    store = "google_play" if re.search(r"google\s+play|play\s+store", plain, re.IGNORECASE) else ""
    if not store and re.search(r"app\s+store|ios|apple", plain, re.IGNORECASE):
        store = "app_store"
    apps_id = _apps_id_from_url(review_url)
    review_id = _review_id_from_strings(strings)
    rating = _extract_rating(plain)
    country = _extract_first([r"\bcountry\D{0,8}([A-Z]{2}|[A-Za-z ]{4,40})", r"\b(MY|SG|ID|PH|TH|VN)\b"], plain)
    app_version = _extract_first([r"\b(?:version|app version|v)\D{0,4}([0-9]+(?:\.[0-9]+){1,4})"], plain)
    reviewer = _extract_first([r"\b(?:reviewer|author|user)\D{0,8}([A-Za-z0-9 _.'-]{2,80})"], plain)
    ext_id = _resolve_ext_id(app_name=app_name, store=store, apps_id=apps_id)
    collection_name = _resolve_collection_name(app_name=app_name, store=store, apps_id=apps_id)
    extracted = {
        "store": store,
        "app_name": app_name,
        "ext_id": ext_id,
        "collection_name": collection_name,
        "apps_id": apps_id,
        "review_id": review_id,
        "title": title,
        "body": body,
        "rating": rating,
        "country": country.upper() if len(country) == 2 else country,
        "app_version": app_version,
        "reviewer": reviewer,
        "appfollow_url": review_url,
        "slack_ts": str(message.get("ts") or ""),
    }
    extracted["dedupe_key"] = review_state_key(extracted)
    return extracted


def _text_blob(review: dict[str, Any]) -> str:
    fields = [
        review.get("title"),
        review.get("body"),
        review.get("text"),
        review.get("content"),
        review.get("review"),
        review.get("app_name"),
    ]
    return " ".join(str(value or "") for value in fields).lower()


def classify_appfollow_review(review: dict[str, Any]) -> dict[str, str]:
    text = _text_blob(review)
    rating = review.get("rating") or review.get("score") or review.get("stars")
    try:
        rating_value = int(rating) if rating is not None else 0
    except (TypeError, ValueError):
        rating_value = 0
    theme = "other"
    theme_markers = [
        ("clock_in", ["clock-in", "clock in", "clockin", "clock", "store clock"]),
        ("scheduling", ["schedule", "shift", "roster"]),
        ("payroll", ["payroll", "pay", "salary", "payslip"]),
        ("leave", ["leave", "time off", "annual leave"]),
        ("login", ["login", "log in", "otp", "password", "sign in"]),
        ("performance", ["slow", "lag", "crash", "hang", "freeze"]),
        ("usability", ["confusing", "hard to use", "cannot find", "missing"]),
    ]
    for candidate, markers in theme_markers:
        if any(marker in text for marker in markers):
            theme = candidate
            break
    severe_markers = ["cannot", "can't", "unable", "missing", "crash", "bug", "broken", "not working", "fail"]
    if rating_value and rating_value <= 2:
        severity = "high"
    elif any(marker in text for marker in severe_markers):
        severity = "high" if rating_value <= 3 or not rating_value else "medium"
    elif rating_value == 3:
        severity = "needs-check"
    else:
        severity = "normal"
    return {"severity": severity, "theme": theme}


def _state_path(path: str = "") -> Path:
    configured = path or _env("PSM_OPS_APPFOLLOW_STATE_PATH") or DEFAULT_STATE_PATH
    return Path(configured).expanduser()


def load_state(path: str = "") -> dict[str, Any]:
    state_file = _state_path(path)
    if not state_file.exists():
        return {"reviews": {}}
    try:
        payload = json.loads(state_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"reviews": {}}
    if not isinstance(payload, dict):
        return {"reviews": {}}
    if not isinstance(payload.get("reviews"), dict):
        payload["reviews"] = {}
    return payload


def save_state(state: dict[str, Any], path: str = "") -> None:
    state_file = _state_path(path)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def review_state_key(review: dict[str, Any]) -> str:
    store = str(review.get("store") or "").strip() or "unknown-store"
    ext_id = str(review.get("ext_id") or review.get("collection_name") or review.get("apps_id") or "").strip() or "unknown-ext"
    review_id = str(review.get("review_id") or review.get("id") or "").strip() or "unknown-review"
    return f"{store}:{ext_id}:{review_id}"


def already_triaged(review: dict[str, Any], *, state_path: str = "") -> bool:
    state = load_state(state_path)
    key = review_state_key(review)
    return key in (state.get("reviews") or {})


def mark_triaged(
    review: dict[str, Any],
    *,
    slack_thread_url: str = "",
    state_path: str = "",
    dry_run: bool = False,
) -> dict[str, Any]:
    key = review_state_key(review)
    entry = {
        "store": review.get("store", ""),
        "ext_id": review.get("ext_id", ""),
        "collection_name": review.get("collection_name", ""),
        "apps_id": review.get("apps_id", ""),
        "review_id": review.get("review_id", ""),
        "slack_thread_url": slack_thread_url,
        "triaged_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        return {"status": "preview", "key": key, "entry": entry}
    state = load_state(state_path)
    reviews = state.setdefault("reviews", {})
    reviews[key] = entry
    save_state(state, state_path)
    return {"status": "stored", "key": key, "entry": entry}


def state_summary(review: dict[str, Any], *, state_path: str = "") -> dict[str, Any]:
    key = review_state_key(review)
    state = load_state(state_path)
    entry = (state.get("reviews") or {}).get(key)
    return {"key": key, "already_triaged": bool(entry), "entry": entry or {}}
