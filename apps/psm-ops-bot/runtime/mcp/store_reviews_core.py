#!/usr/bin/env python3
"""AppFollow review helpers for PSM Ops Bot.

This module is shared by the MCP adapter and the no-agent polling script.
AppFollow is the review source for this packet. Slack is the PS Wee action
surface, and public reply publishing is not exposed in V1.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


STORE_REVIEWS_SOURCE = "AppFollow Reviews API"
USER_AGENT = "StaffAny-PSMOps/1.0 (+https://staffany.com)"
TIMEOUT_SECONDS = 20
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_MAX_PAGES = 5
DEFAULT_STATE_PATH = "~/.hermes/profiles/psmopsbot/state/store_reviews.json"
DEFAULT_APPFOLLOW_CREDENTIALS_FILE = "~/.staffany/appfollow/credentials.json"
STATE_KEY_DESCRIPTION = "store + app_ref + review_id"
STAFFANY_SUPPORT_EMAIL = "support@staffany.com"
MAX_REPLY_CHARS = 350
APPFOLLOW_BASE_URL = "https://api.appfollow.io"
IDENTITY_LABEL_UNKNOWN = "identity_unknown"
IDENTITY_LABEL_REQUESTED_PRIVATE = "identity_requested_private"
IDENTITY_LABEL_CANDIDATE = "identity_candidate"
IDENTITY_LABEL_CONFIRMED = "identity_confirmed"


class StoreReviewError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _safe_detail(value: Any, limit: int = 400) -> str:
    text = " ".join(str(value or "").split())
    for key in [
        "APPFOLLOW_API_TOKEN",
    ]:
        secret = os.environ.get(key, "")
        if secret:
            text = text.replace(secret, "[redacted]")
    text = re.sub(r"-----BEGIN [^-]+-----.*?-----END [^-]+-----", "[redacted-private-key]", text, flags=re.DOTALL)
    text = re.sub(r"\b[A-Za-z0-9_-]{24,}\b", "[redacted]", text)
    return text[:limit]


def _request_json(
    method: str,
    url: str,
    *,
    access_token: str = "",
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    full_url = f"{url}?{query}" if query else url
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"accept": "application/json", "user-agent": USER_AGENT}
    headers.update(extra_headers or {})
    if data is not None:
        headers["content-type"] = "application/json; charset=utf-8"
    if access_token:
        headers["authorization"] = f"Bearer {access_token}"
    request = urllib.request.Request(full_url, data=data, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise StoreReviewError(f"Store review API failed: HTTP {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise StoreReviewError(f"Store review API request timed out or failed: {_safe_detail(reason)}") from error


def blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": {"status": "blocked", "message": message},
        "source": STORE_REVIEWS_SOURCE,
        "scope": scope or {},
        "confidence": "blocked",
        "caveat": message,
    }


def tool_result(
    answer: Any,
    scope: dict[str, Any],
    *,
    confidence: str = "needs-check",
    caveat: str = "AppFollow is the review provider. Slack remains the PS Wee triage surface.",
) -> dict[str, Any]:
    return {
        "answer": answer,
        "source": STORE_REVIEWS_SOURCE,
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


def _appfollow_credentials() -> dict[str, Any]:
    token = _env("APPFOLLOW_API_TOKEN")
    credentials_file = _env("PSM_OPS_APPFOLLOW_CREDENTIALS_FILE") or _env("APPFOLLOW_CREDENTIALS_FILE")
    if token:
        return {
            "appfollow_api_token": token,
            "collection_name": _env("APPFOLLOW_COLLECTION_NAME"),
            "ext_ids": _env("APPFOLLOW_EXT_IDS"),
        }
    path = Path(credentials_file or DEFAULT_APPFOLLOW_CREDENTIALS_FILE).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise StoreReviewError(f"AppFollow credentials file is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise StoreReviewError(f"AppFollow credentials file is invalid JSON: {path}") from error
    if not isinstance(payload, dict):
        raise StoreReviewError(f"AppFollow credentials file must contain a JSON object: {path}")
    if not str(payload.get("appfollow_api_token") or "").strip():
        raise StoreReviewError("AppFollow credentials need appfollow_api_token.")
    return payload


def _appfollow_token() -> str:
    return str(_appfollow_credentials().get("appfollow_api_token") or "").strip()


def _appfollow_app_refs() -> list[str]:
    credentials = _appfollow_credentials()
    raw_refs = credentials.get("ext_ids") or credentials.get("app_ext_ids") or _env("APPFOLLOW_EXT_IDS")
    if isinstance(raw_refs, list):
        refs = [str(item).strip() for item in raw_refs]
    else:
        refs = [item.strip() for item in str(raw_refs or "").split(",")]
    refs = [item for item in refs if item]
    collection = str(credentials.get("collection_name") or _env("APPFOLLOW_COLLECTION_NAME") or "").strip()
    if refs:
        return refs
    if collection:
        return [f"collection:{collection}"]
    raise StoreReviewError("AppFollow credentials need ext_ids/app_ext_ids or collection_name.")


def _appfollow_review_window(lookback_days: int) -> tuple[str, str]:
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(1, int(lookback_days or DEFAULT_LOOKBACK_DAYS)))
    return start.isoformat(), end.isoformat()


def _appfollow_request(params: dict[str, Any]) -> dict[str, Any]:
    return _request_json(
        "GET",
        f"{APPFOLLOW_BASE_URL}/api/v2/reviews",
        params=params,
        extra_headers={"X-AppFollow-API-Token": _appfollow_token()},
    )


def _extract_appfollow_reviews(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ("reviews", "data", "items", "results", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _extract_appfollow_reviews(value)
            if nested:
                return nested
    if any(key in payload for key in ("review_id", "id", "content", "review")):
        return [payload]
    return []


def normalize_appfollow_review(review: dict[str, Any], app_ref: str = "") -> dict[str, Any]:
    store = normalize_store(
        str(review.get("store") or review.get("platform") or review.get("source") or review.get("store_type") or "")
    )
    if store not in {"google_play", "app_store"}:
        store = "appfollow"
    review_id = str(review.get("review_id") or review.get("reviewId") or review.get("id") or "").strip()
    rating = review.get("rating") or review.get("review_rating") or review.get("stars") or review.get("rate")
    try:
        rating = int(float(rating)) if rating not in (None, "") else None
    except (TypeError, ValueError):
        rating = None
    created_at = str(
        review.get("created_at")
        or review.get("created")
        or review.get("date")
        or review.get("review_date")
        or review.get("published_at")
        or ""
    ).strip()
    updated_at = str(review.get("updated_at") or review.get("last_modified") or review.get("modified_at") or created_at).strip()
    resolved_app_ref = str(
        app_ref
        or review.get("ext_id")
        or review.get("app_id")
        or review.get("application_id")
        or review.get("app")
        or ""
    ).strip()
    answer_text = str(review.get("answer_text") or review.get("reply") or review.get("response") or "").strip()
    return {
        "store": store,
        "app_ref": resolved_app_ref,
        "review_id": review_id,
        "rating": rating,
        "title": str(review.get("title") or review.get("subject") or "").strip(),
        "body": str(review.get("content") or review.get("review") or review.get("body") or review.get("text") or "").strip(),
        "author_nickname": str(review.get("author") or review.get("user_name") or review.get("reviewer") or "").strip(),
        "country": str(review.get("country") or "").strip(),
        "locale": str(review.get("lang") or review.get("language") or "").strip(),
        "app_version": str(review.get("version") or review.get("app_version") or "").strip(),
        "created_at": created_at,
        "updated_at": updated_at,
        "reply_status": "replied" if answer_text else str(review.get("reply_status") or "no_reply").strip(),
        "review_url": str(review.get("url") or review.get("review_url") or "").strip(),
        "raw": review,
    }


def list_store_review_apps() -> dict[str, Any]:
    scope = {"endpoint": "appfollow", "provider": "appfollow"}
    try:
        apps = [
            {
                "store": "appfollow",
                "app_ref": app_ref,
                "credential_source": "APPFOLLOW_API_TOKEN or APPFOLLOW_CREDENTIALS_FILE",
                "required_permission": "Read",
            }
            for app_ref in _appfollow_app_refs()
        ]
    except StoreReviewError as error:
        return blocked(str(error), scope)
    return tool_result(
        {"status": "configured", "provider": "appfollow", "apps": apps},
        scope,
        confidence="verified",
        caveat="AppFollow is the review provider. Use a Read-only token.",
    )


def list_store_reviews(
    *,
    store: str = "",
    app_ref: str = "",
    limit: int = 20,
    page_token: str = "",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_pages: int = DEFAULT_MAX_PAGES,
) -> dict[str, Any]:
    safe_limit = max(1, min(int(limit or 20), 100))
    safe_max_pages = max(1, min(int(max_pages or DEFAULT_MAX_PAGES), 10))
    from_date, to_date = _appfollow_review_window(lookback_days)
    try:
        app_refs = [app_ref] if app_ref else _appfollow_app_refs()
    except StoreReviewError as error:
        return blocked(str(error), {"provider": "appfollow", "stores": [store] if store else ["appfollow"]})
    reviews: list[dict[str, Any]] = []
    store_errors: list[dict[str, Any]] = []
    next_page_tokens: dict[str, str] = {}
    scope = {
        "provider": "appfollow",
        "stores": [store] if store else ["appfollow"],
        "app_refs": app_refs,
        "limit": safe_limit,
        "lookback_days": lookback_days,
        "max_pages": safe_max_pages,
    }
    try:
        start_page = int(str(page_token or "1").strip())
    except ValueError:
        return blocked("AppFollow page_token must be an integer page number.", scope)
    for current_ref in app_refs:
        is_collection = current_ref.startswith("collection:")
        collection_name = current_ref.split(":", 1)[1] if is_collection else ""
        page = max(1, start_page)
        try:
            for _page in range(safe_max_pages):
                params: dict[str, Any] = {"from": from_date, "to": to_date, "page": page}
                if is_collection:
                    params["collection_name"] = collection_name
                else:
                    params["ext_id"] = current_ref
                if store:
                    params["store"] = normalize_store(store)
                payload = _appfollow_request(params)
                page_reviews = _extract_appfollow_reviews(payload)
                for item in page_reviews:
                    reviews.append(normalize_appfollow_review(item, current_ref))
                if len(page_reviews) < safe_limit:
                    break
                page += 1
            if page > start_page:
                next_page_tokens[current_ref] = str(page)
        except StoreReviewError as error:
            store_errors.append({"store": "appfollow", "app_ref": current_ref, "message": str(error), "status_code": error.status_code})
    if store_errors and len(store_errors) == len(app_refs):
        return blocked("All configured AppFollow review sources failed.", {**scope, "store_errors": store_errors})
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(lookback_days or DEFAULT_LOOKBACK_DAYS)))
    bounded = [review for review in reviews if _within_lookback(review, cutoff)][:safe_limit]
    return tool_result(
        {"status": "ok", "provider": "appfollow", "reviews": bounded, "next_page_tokens": next_page_tokens, "store_errors": store_errors},
        scope,
        confidence="needs-check" if store_errors else "verified",
        caveat=(
            "One or more AppFollow review sources failed; available reviews are from sources that responded."
            if store_errors
            else "AppFollow is the review provider. Slack remains the PS Wee triage surface."
        ),
    )


def get_store_review(*, store: str, review_id: str, app_ref: str = "") -> dict[str, Any]:
    current_store = normalize_store(store)
    review_id = str(review_id or "").strip()
    scope = {"provider": "appfollow", "store": current_store, "app_ref": app_ref, "review_id": review_id}
    if not current_store or not review_id:
        return blocked("store and review_id are required before fetching a store review.", scope)
    try:
        from_date, to_date = _appfollow_review_window(DEFAULT_LOOKBACK_DAYS)
        refs = [app_ref] if app_ref else _appfollow_app_refs()
        selected_review = None
        for current_ref in refs:
            params: dict[str, Any] = {"from": from_date, "to": to_date, "review_id": review_id}
            if current_ref.startswith("collection:"):
                params["collection_name"] = current_ref.split(":", 1)[1]
            else:
                params["ext_id"] = current_ref
            payload = _appfollow_request(params)
            matches = _extract_appfollow_reviews(payload)
            if matches:
                selected_review = normalize_appfollow_review(matches[0], current_ref)
                break
        if not selected_review:
            return blocked("AppFollow did not return the requested review.", scope)
        review = selected_review
    except StoreReviewError as error:
        return blocked(str(error), scope)
    return tool_result({"status": "ok", "review": review}, scope, confidence="verified")


def normalize_store(store: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(store or "").strip().lower()).strip("_")
    aliases = {
        "google": "google_play",
        "play": "google_play",
        "play_store": "google_play",
        "googleplay": "google_play",
        "android": "google_play",
        "ios": "app_store",
        "apple": "app_store",
        "appstore": "app_store",
        "app_store_connect": "app_store",
    }
    return aliases.get(raw, raw)


def _parse_datetime(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _within_lookback(review: dict[str, Any], cutoff: datetime) -> bool:
    parsed = _parse_datetime(str(review.get("updated_at") or review.get("created_at") or ""))
    if parsed is None:
        return True
    return parsed >= cutoff


def _review_text_from_payload(review: dict[str, Any]) -> str:
    candidates = [review.get("title"), review.get("body"), review.get("text"), review.get("content"), review.get("review")]
    return " ".join(str(value or "") for value in candidates if str(value or "").strip()).strip()


def _shorten(text: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", text or "").strip()
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "..."


def _public_private_contact_cta() -> str:
    return (
        f"Please email {STAFFANY_SUPPORT_EMAIL} with your StaffAny account email or phone number, "
        "plus your company/outlet, so we can follow up privately."
    )


def draft_store_review_reply(review: dict[str, Any] | None = None, issue_summary: str = "") -> dict[str, Any]:
    review = review or {}
    text = _review_text_from_payload(review)
    title = str(review.get("title") or "").strip()
    theme = classify_store_review(review).get("theme") or "app experience"
    issue = _shorten(issue_summary or title or text or f"{theme} issue", 90)
    reply = f"Thanks for flagging this. We are checking the issue on our side ({issue}). {_public_private_contact_cta()}"
    if len(reply) > MAX_REPLY_CHARS:
        reply = _shorten(reply, MAX_REPLY_CHARS)
    scope = {
        "store": review.get("store", ""),
        "app_ref": review.get("app_ref", ""),
        "review_id": review.get("review_id", ""),
        "theme": theme,
        "support_email": STAFFANY_SUPPORT_EMAIL,
        "publish_tool": "not_exposed_in_v1",
    }
    return tool_result(
        {"status": "draft", "answer_text": reply, "support_email": STAFFANY_SUPPORT_EMAIL},
        scope,
        confidence="draft",
        caveat=(
            "Draft only. Public store reply publishing is intentionally not exposed in V1. "
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
        "company_or_outlet": str(company_or_outlet or claim.get("company_or_outlet") or claim.get("company") or claim.get("outlet") or "").strip(),
        "reviewer_nickname": str(reviewer_nickname or claim.get("reviewer_nickname") or claim.get("reviewer") or "").strip(),
        "review_text": str(review_text or claim.get("review_text") or claim.get("text") or "").strip(),
    }


def suggest_store_review_identity_candidates(
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
    review_key = review_state_key(review)
    scope = {
        "review_key": review_key,
        "review_id": str(review.get("review_id") or "").strip(),
        "state_key": STATE_KEY_DESCRIPTION,
        "signals": {
            "email": bool(normalized_email),
            "phone": bool(normalized_phone),
            "company_or_outlet": bool(claim["company_or_outlet"]),
            "reviewer_nickname": bool(claim["reviewer_nickname"]),
            "review_text": bool(claim["review_text"] or _review_text_from_payload(review)),
        },
        "slack_thread_url": slack_thread_url,
    }
    if not any([normalized_email, normalized_phone, claim["company_or_outlet"]]):
        return tool_result(
            {
                "status": "unknown",
                "review_key": review_key,
                "candidates": [],
                "internal_labels": [IDENTITY_LABEL_UNKNOWN, IDENTITY_LABEL_REQUESTED_PRIVATE],
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
            key = f"email:{normalized_email}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(
                    {
                        "match_type": "exact_email",
                        "confidence": "verified",
                        "source": "Customer 360 candidate evidence",
                        "customer": group_summary,
                        "contact": {"email": _redact_email(normalized_email)},
                        "reason": "Private support email exactly matches Customer 360/HubSpot candidate evidence.",
                    }
                )
        if normalized_phone and normalized_phone in group_phones:
            key = f"phone:{normalized_phone}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(
                    {
                        "match_type": "phone",
                        "confidence": "needs-check",
                        "source": "Customer 360 candidate evidence",
                        "customer": group_summary,
                        "contact": {"phone": _redact_phone(normalized_phone)},
                        "reason": "Phone appears in Customer 360 candidate evidence, but phone-only linkage is ambiguous until human-confirmed.",
                    }
                )
        if claim["company_or_outlet"]:
            key = f"company:{claim['company_or_outlet'].lower()}:{key_seed}"
            if key not in seen_candidates:
                seen_candidates.add(key)
                candidates.append(
                    {
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
                )

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
    return tool_result(
        {
            "status": status,
            "review_key": review_key,
            "c360_status": c360_status,
            "candidates": candidates,
            "internal_labels": [IDENTITY_LABEL_CANDIDATE],
            "confirmation_tool": "confirm_store_review_identity",
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


def confirm_store_review_identity(
    *,
    review: dict[str, Any] | None = None,
    review_key: str = "",
    store: str = "",
    app_ref: str = "",
    review_id: str = "",
    customer_key: str = "",
    customer_name: str = "",
    contact_email: str = "",
    contact_phone: str = "",
    confirmation_text: str = "",
    confirmed_by: str = "",
    state_path: str = "",
) -> dict[str, Any]:
    key = review_key or review_state_key({**(review or {}), "store": store or (review or {}).get("store"), "app_ref": app_ref or (review or {}).get("app_ref"), "review_id": review_id or (review or {}).get("review_id")})
    scope = {"review_key": key, "state_key": STATE_KEY_DESCRIPTION, "customer_key": customer_key, "customer_name": customer_name}
    if not key or key.endswith(":unknown-review"):
        return blocked("review_id or review_key is required before confirming reviewer identity.", scope)
    if not (customer_key or customer_name):
        return blocked("customer_key or customer_name is required before confirming reviewer identity.", scope)
    if not confirmation_text.strip():
        return blocked("confirmation_text is required so the human approval evidence is recorded.", scope)
    confirmation = {
        "status": IDENTITY_LABEL_CONFIRMED,
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
    state.setdefault("identity_confirmations", {})[key] = confirmation
    review_entry = state.setdefault("reviews", {}).setdefault(key, {})
    review_entry["identity_status"] = IDENTITY_LABEL_CONFIRMED
    review_entry["identity_confirmed_at"] = confirmation["confirmed_at"]
    save_state(state, state_path)
    return tool_result(
        {"status": IDENTITY_LABEL_CONFIRMED, "review_key": key, "confirmation": confirmation, "internal_labels": [IDENTITY_LABEL_CONFIRMED]},
        scope,
        confidence="verified",
        caveat="Stored only the human-confirmed mapping and redacted contact hints in runtime state outside git.",
    )


def classify_store_review(review: dict[str, Any]) -> dict[str, str]:
    fields = [review.get("title"), review.get("body"), review.get("text"), review.get("content"), review.get("review")]
    text = " ".join(str(value or "") for value in fields).lower()
    rating = review.get("rating") or review.get("score") or review.get("stars")
    try:
        rating_value = int(rating) if rating is not None else 0
    except (TypeError, ValueError):
        rating_value = 0
    theme = "other"
    for candidate, markers in [
        ("clock_in", ["clock-in", "clock in", "clockin", "clock", "store clock"]),
        ("scheduling", ["schedule", "shift", "roster"]),
        ("payroll", ["payroll", "pay", "salary", "payslip"]),
        ("leave", ["leave", "time off", "annual leave"]),
        ("login", ["login", "log in", "otp", "password", "sign in"]),
        ("performance", ["slow", "lag", "crash", "hang", "freeze"]),
        ("usability", ["confusing", "hard to use", "cannot find", "missing"]),
    ]:
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
    configured = path or _env("PSM_OPS_STORE_REVIEWS_STATE_PATH") or DEFAULT_STATE_PATH
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
    payload = json.dumps(state, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=state_file.parent, delete=False) as handle:
            temp_path = handle.name
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, state_file)
    finally:
        if temp_path:
            try:
                Path(temp_path).unlink(missing_ok=True)
            except OSError:
                pass


def review_state_key(review: dict[str, Any]) -> str:
    store = normalize_store(str(review.get("store") or "")) or "unknown-store"
    app_ref = str(review.get("app_ref") or review.get("package_name") or review.get("app_id") or "").strip() or "unknown-app"
    review_id = str(review.get("review_id") or review.get("id") or "").strip() or "unknown-review"
    return f"{store}:{app_ref}:{review_id}"


def review_fingerprint(review: dict[str, Any]) -> str:
    payload = {
        "rating": review.get("rating"),
        "title": review.get("title"),
        "body": review.get("body"),
        "reply_status": review.get("reply_status"),
        "updated_at": review.get("updated_at") or review.get("created_at"),
    }
    return hashlib.sha256(json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def state_summary(review: dict[str, Any], *, state_path: str = "") -> dict[str, Any]:
    key = review_state_key(review)
    state = load_state(state_path)
    entry = (state.get("reviews") or {}).get(key)
    fingerprint = review_fingerprint(review)
    return {
        "key": key,
        "already_triaged": bool(entry and entry.get("fingerprint") == fingerprint),
        "changed": bool(entry and entry.get("fingerprint") != fingerprint),
        "fingerprint": fingerprint,
        "entry": entry or {},
    }


def already_triaged(review: dict[str, Any], *, state_path: str = "") -> bool:
    return bool(state_summary(review, state_path=state_path)["already_triaged"])


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
        "app_ref": review.get("app_ref", ""),
        "review_id": review.get("review_id", ""),
        "rating": review.get("rating"),
        "updated_at": review.get("updated_at", ""),
        "fingerprint": review_fingerprint(review),
        "slack_thread_url": slack_thread_url,
        "triaged_at": datetime.now(timezone.utc).isoformat(),
    }
    if dry_run:
        return {"status": "preview", "key": key, "entry": entry}
    state = load_state(state_path)
    state.setdefault("reviews", {})[key] = entry
    save_state(state, state_path)
    return {"status": "stored", "key": key, "entry": entry}


def poll_new_reviews(*, store: str = "", limit: int = 20, lookback_days: int = DEFAULT_LOOKBACK_DAYS, state_path: str = "", include_changed: bool = True) -> dict[str, Any]:
    result = list_store_reviews(store=store, limit=limit, lookback_days=lookback_days)
    if result.get("confidence") == "blocked":
        return result
    answer = (result.get("answer") or {}) if isinstance(result, dict) else {}
    reviews = answer.get("reviews") or []
    store_errors = answer.get("store_errors") or []
    candidates: list[dict[str, Any]] = []
    skipped: list[str] = []
    for review in reviews:
        summary = state_summary(review, state_path=state_path)
        if summary["already_triaged"]:
            skipped.append(summary["key"])
            continue
        if not include_changed and summary["changed"]:
            skipped.append(summary["key"])
            continue
        candidates.append({**review, "state_key": summary["key"], "changed_since_last_triage": summary["changed"]})
    return tool_result(
        {"status": "ok", "reviews": candidates, "skipped_duplicate_keys": skipped, "store_errors": store_errors},
        {"store": store or "all", "limit": limit, "lookback_days": lookback_days, "state_key": STATE_KEY_DESCRIPTION},
        confidence="needs-check" if store_errors else "verified",
        caveat=(
            "One or more store review sources failed; available reviews are from the stores that responded."
            if store_errors
            else "AppFollow is the review provider. Slack remains the PS Wee triage surface."
        ),
    )


def build_slack_triage_text(review: dict[str, Any], *, changed: bool = False) -> str:
    classification = classify_store_review(review)
    draft = draft_store_review_reply(review)
    answer_text = ((draft.get("answer") or {}) if isinstance(draft, dict) else {}).get("answer_text", "")
    rating = review.get("rating")
    stars = f"{rating}/5" if rating else "unknown rating"
    title = review.get("title") or _shorten(review.get("body", ""), 80) or "Untitled review"
    app_version = review.get("app_version") or "unknown app version"
    country = review.get("country") or review.get("locale") or "unknown country/locale"
    state_note = "Updated review detected" if changed else "New review detected"
    lines = [
        "PSM Ops automation: Store review triage",
        f"{state_note}: {stars} {review.get('store') or 'unknown store'} {country} {app_version} - {_shorten(str(title), 120)}",
        f"Review ID: {review.get('review_id') or 'missing'}",
        f"App ref: {review.get('app_ref') or 'missing'}",
        f"Theme: {classification['theme']} | Severity: {classification['severity']}",
        f"Review link: {review.get('review_url') or 'n/a'}",
        (
            f"Actions: request private contact details via {STAFFANY_SUPPORT_EMAIL}, mark internal label "
            f"`{IDENTITY_LABEL_REQUESTED_PRIVATE}`, and watch for support follow-up. Public store reply publishing is not enabled in V1."
        ),
        (
            "Identity: unknown until the reviewer follows up privately with their StaffAny account email or phone "
            "plus company/outlet. Do not ask for email/phone in the public review."
        ),
        f"Internal correlation: {review_state_key(review)}",
        f"Draft reply for approval: {_shorten(answer_text, 300)}",
        "Caveat: reviewer nickname is not enough to map a StaffAny customer/org. Use private support follow-up plus Customer 360/Jira evidence for internal follow-up.",
    ]
    return "\n".join(lines)
