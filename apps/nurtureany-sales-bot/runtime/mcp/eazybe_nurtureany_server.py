#!/usr/bin/env python3
"""Approval-gated Eazybe MCP adapter for NurtureAny Sales Bot.

This server only handles approved WhatsApp template payloads. Free-form drafts
remain preview text unless they are mapped into approved Eazybe template
variables. Slack output is phone-redacted by default.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.responses import blocked_response, safe_detail as _safe_detail


EAZYBE_API_KEY_ENV = "EAZYBE_API_KEY"
EAZYBE_BROADCAST_API_URL_ENV = "EAZYBE_BROADCAST_API_URL"
EAZYBE_STATUS_API_URL_ENV = "EAZYBE_STATUS_API_URL"
EAZYBE_TIMEOUT_SECONDS = 15
EAZYBE_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
NURTUREANY_DAILY_RUNS_DIR_ENV = "NURTUREANY_DAILY_RUNS_DIR"
SENT_STATUSES = {"accepted", "queued", "sent", "delivered"}
TERMINAL_FAILURE_STATUSES = {"failed", "rejected", "undeliverable", "error"}
PHONE_PATTERN = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{6,}\d)(?!\w)")


mcp = FastMCP(
    "eazybe_nurtureany",
    instructions=(
        "Approval-gated Eazybe WhatsApp template adapter for NurtureAny. Preview first, "
        "send only selected approved template message IDs with approval_marker, redact phone numbers, "
        "and never send free-form drafts."
    ),
)


class EazybeError(RuntimeError):
    pass


def _scope(run_id: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "run_id": run_id,
        "eazybe_access_mode": "approval_gated_template_send",
        "phone_numbers_redacted": True,
        "free_form_drafts_sendable": False,
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "Eazybe", scope)


def _api_key() -> str:
    return os.environ.get(EAZYBE_API_KEY_ENV, "").strip()


def _broadcast_api_url() -> str:
    return os.environ.get(EAZYBE_BROADCAST_API_URL_ENV, "").strip()


def _status_api_url() -> str:
    return os.environ.get(EAZYBE_STATUS_API_URL_ENV, "").strip()


def _runs_dir() -> Path | None:
    raw = os.environ.get(NURTUREANY_DAILY_RUNS_DIR_ENV, "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def _load_run_messages(run_id: str) -> list[dict[str, Any]]:
    runs_dir = _runs_dir()
    if not runs_dir:
        return []
    safe_name = re.sub(r"[^A-Za-z0-9_.:-]+", "_", run_id or "")
    path = runs_dir / f"{safe_name}.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    if isinstance(payload, dict):
        answer = payload.get("answer") if isinstance(payload.get("answer"), dict) else payload
        messages = answer.get("messages")
    else:
        messages = payload
    return [message for message in messages or [] if isinstance(message, dict)]


def _selected_messages(
    run_id: str,
    message_ids: list[str] | None,
    messages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    selected_ids = [str(message_id or "").strip() for message_id in message_ids or [] if str(message_id or "").strip()]
    available_messages = [message for message in messages or [] if isinstance(message, dict)]
    if not available_messages:
        available_messages = _load_run_messages(run_id)
    if not selected_ids:
        return [], []
    by_id = {str(message.get("message_id") or ""): message for message in available_messages}
    selected = [by_id[message_id] for message_id in selected_ids if message_id in by_id]
    missing = [message_id for message_id in selected_ids if message_id not in by_id]
    return selected, missing


def _redact_phone(value: Any) -> Any:
    if isinstance(value, str):
        def replace(match: re.Match[str]) -> str:
            text = match.group(0)
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text.strip()):
                return text
            digits = re.sub(r"\D+", "", text)
            if len(digits) < 8:
                return text
            return "[redacted-phone]"

        return PHONE_PATTERN.sub(replace, value)
    if isinstance(value, list):
        return [_redact_phone(item) for item in value]
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if "phone" in str(key).lower() or "mobile" in str(key).lower():
                redacted[key] = "[redacted-phone]" if item else ""
            else:
                redacted[key] = _redact_phone(item)
        return redacted
    return value


def _template_payload(message: dict[str, Any]) -> dict[str, Any]:
    payload = message.get("template_payload") if isinstance(message.get("template_payload"), dict) else {}
    return payload


def _template_name(message: dict[str, Any]) -> str:
    payload = _template_payload(message)
    return str(payload.get("template_name") or message.get("template_name") or "").strip()


def _template_schema(message: dict[str, Any]) -> list[str]:
    payload = _template_payload(message)
    raw = payload.get("template_params_schema") or message.get("template_params_schema") or []
    if isinstance(raw, list):
        return [str(item or "").strip() for item in raw if str(item or "").strip()]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item or "").strip() for item in parsed if str(item or "").strip()]
    except json.JSONDecodeError:
        pass
    return [part.strip() for part in re.split(r"[,;|]", text) if part.strip()]


def _template_params(message: dict[str, Any]) -> list[str]:
    payload = _template_payload(message)
    raw = payload.get("template_params") or message.get("template_params") or []
    if not isinstance(raw, list):
        return []
    return [str(item or "") for item in raw]


def _validate_template_message(message: dict[str, Any]) -> list[str]:
    errors = []
    template_name = _template_name(message)
    params = _template_params(message)
    schema = _template_schema(message)
    if not template_name:
        errors.append("missing approved template_name")
    if not message.get("eazybe_ready", True):
        errors.append("message is not marked eazybe_ready")
    if schema and len(params) != len(schema):
        errors.append(f"template param count mismatch: expected {len(schema)}, got {len(params)}")
    if not params:
        errors.append("missing ordered templateParams")
    return errors


def _safe_preview_message(message: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "message_id": message.get("message_id") or "",
        "company_id": message.get("company_id") or "",
        "company_name": message.get("company_name") or "",
        "contact_id": message.get("contact_id") or "",
        "stakeholder_name": message.get("stakeholder_name") or "",
        "stakeholder_role": message.get("stakeholder_role") or "",
        "role_confidence": message.get("role_confidence") or "",
        "material": message.get("material") or {},
        "draft_preview": message.get("draft_preview") or "",
        "template_payload": {
            "template_name": _template_name(message),
            "template_params_schema": _template_schema(message),
            "templateParams": _template_params(message),
        },
        "validation_errors": _validate_template_message(message),
    }
    return _redact_phone(payload)


def _recipient_ref(message: dict[str, Any]) -> str:
    return str(message.get("recipient_ref") or message.get("contact_id") or message.get("message_id") or "").strip()


def _recipient_phone(message: dict[str, Any]) -> str:
    return str(message.get("recipient_phone") or message.get("phone") or "").strip()


def _broadcast_payload(run_id: str, message: dict[str, Any]) -> dict[str, Any]:
    return {
        "runId": run_id,
        "messageId": message.get("message_id") or "",
        "recipient": {
            "ref": _recipient_ref(message),
            "phone": _recipient_phone(message),
        },
        "templateName": _template_name(message),
        "templateParams": _template_params(message),
    }


def _send_eazybe_message(run_id: str, message: dict[str, Any]) -> dict[str, Any]:
    api_key = _api_key()
    url = _broadcast_api_url()
    if not api_key:
        raise EazybeError(f"Missing {EAZYBE_API_KEY_ENV}.")
    if not url:
        raise EazybeError(f"Missing {EAZYBE_BROADCAST_API_URL_ENV}.")
    body = json.dumps(_broadcast_payload(run_id, message)).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "authorization": f"Bearer {api_key}",
            "content-type": "application/json",
            "accept": "application/json",
            "user-agent": EAZYBE_USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=EAZYBE_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            payload = json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise EazybeError(f"Eazybe Broadcast API failed: {error.code} {_safe_detail(detail)}") from error
    except (urllib.error.URLError, socket.timeout, TimeoutError, json.JSONDecodeError) as error:
        raise EazybeError(f"Eazybe Broadcast API request failed: {error}") from error
    status = "queued" if 200 <= int(getattr(response, "status", 200)) < 300 else "failed"
    return {
        "message_id": message.get("message_id") or "",
        "status": status,
        "provider_message_id": str(payload.get("id") or payload.get("messageId") or payload.get("broadcastId") or ""),
        "recipient_ref": _recipient_ref(message),
    }


def _status_by_message_id(statuses: list[dict[str, Any]] | dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if isinstance(statuses, dict):
        raw_statuses = statuses.get("messages") if isinstance(statuses.get("messages"), list) else statuses.get("statuses")
        if raw_statuses is None and statuses.get("message_id"):
            raw_statuses = [statuses]
    else:
        raw_statuses = statuses
    by_id = {}
    for item in raw_statuses or []:
        if not isinstance(item, dict):
            continue
        message_id = str(item.get("message_id") or item.get("messageId") or "").strip()
        if message_id:
            by_id[message_id] = item
    return by_id


def _message_status(message: dict[str, Any], statuses: dict[str, dict[str, Any]]) -> str:
    explicit = str(message.get("send_status") or "").strip().lower()
    status = statuses.get(str(message.get("message_id") or ""))
    if status:
        explicit = str(status.get("status") or status.get("send_status") or explicit).strip().lower()
    if explicit:
        return explicit
    return "pending"


def _unsent_unskipped_messages(
    messages: list[dict[str, Any]],
    statuses: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    by_id = _status_by_message_id(statuses)
    unsent = []
    for message in messages:
        status = _message_status(message, by_id)
        skipped = bool(message.get("skipped") or message.get("explicitly_skipped"))
        if status in SENT_STATUSES or status == "skipped" or skipped:
            continue
        unsent.append(message)
    return unsent


def _build_reminder_text(
    run_id: str,
    messages: list[dict[str, Any]],
    statuses: list[dict[str, Any]] | dict[str, Any] | None,
    ae_slack_user_id: str,
    manager_slack_user_id: str,
) -> tuple[str, list[dict[str, Any]]]:
    unsent = _unsent_unskipped_messages(messages, statuses)
    mentions = " ".join([mention for mention in [f"<@{ae_slack_user_id}>" if ae_slack_user_id else "", f"<@{manager_slack_user_id}>" if manager_slack_user_id else ""] if mention])
    lines = [f"{mentions} Daily NurtureAny reminder for `{run_id}`: {len(unsent)} stakeholder message(s) still not sent or explicitly skipped.".strip()]
    for message in unsent[:10]:
        lines.append(
            f"- `{message.get('message_id')}` {message.get('company_name') or ''} / {message.get('stakeholder_name') or ''} ({message.get('stakeholder_role') or 'stakeholder'})"
        )
    if len(unsent) > 10:
        lines.append(f"- ...and {len(unsent) - 10} more.")
    return "\n".join(lines), unsent


@mcp.tool()
def preview_eazybe_template_messages(
    run_id: str,
    message_ids: list[str],
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Preview selected Eazybe template messages. This tool never sends WhatsApp."""

    selected, missing = _selected_messages(run_id, message_ids, messages)
    if not selected:
        return _blocked("No selected message_ids were found for preview.", _scope(run_id, {"missing_message_ids": missing}))
    preview = [_safe_preview_message(message) for message in selected]
    preview_id = hashlib.sha256(json.dumps(preview, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    invalid = [message for message in preview if message.get("validation_errors")]
    return {
        "answer": {
            "preview_id": preview_id,
            "run_id": run_id,
            "messages": preview,
            "selected_count": len(preview),
            "invalid_count": len(invalid),
            "missing_message_ids": missing,
            "will_send": False,
        },
        "source": "Eazybe approved-template preview",
        "scope": _scope(run_id, {"selected_message_ids": list(message_ids or [])}),
        "confidence": "needs-check" if invalid or missing else "verified",
        "caveat": "Preview only. Phone numbers are redacted. Sending requires send_approved_eazybe_messages with approval_marker.",
    }


@mcp.tool()
def send_approved_eazybe_messages(
    run_id: str,
    message_ids: list[str],
    approval_marker: str = "",
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Send selected approved Eazybe template messages after explicit approval_marker."""

    selected, missing = _selected_messages(run_id, message_ids, messages)
    scope = _scope(run_id, {"selected_message_ids": list(message_ids or []), "approval_marker_present": bool(approval_marker)})
    if not approval_marker:
        return _blocked("approval_marker is required before any Eazybe send.", scope)
    if not selected:
        return _blocked("No selected message_ids were found for send.", {**scope, "missing_message_ids": missing})

    results = []
    for message in selected:
        errors = _validate_template_message(message)
        if errors:
            results.append(
                {
                    "message_id": message.get("message_id") or "",
                    "status": "blocked",
                    "recipient_ref": _recipient_ref(message),
                    "errors": errors,
                }
            )
            continue
        try:
            results.append(_send_eazybe_message(run_id, message))
        except EazybeError as error:
            results.append(
                {
                    "message_id": message.get("message_id") or "",
                    "status": "failed",
                    "recipient_ref": _recipient_ref(message),
                    "errors": [str(error)],
                }
            )

    accepted = [result for result in results if str(result.get("status") or "").lower() in SENT_STATUSES]
    failures = [result for result in results if result not in accepted]
    return {
        "answer": {
            "run_id": run_id,
            "results": _redact_phone(results),
            "accepted_or_queued_count": len(accepted),
            "failed_or_blocked_count": len(failures),
            "missing_message_ids": missing,
        },
        "source": "Eazybe Broadcast API approved template send",
        "scope": scope,
        "confidence": "verified" if accepted and not failures and not missing else "needs-check",
        "caveat": "Sent means Eazybe accepted/queued the approved template message. Phone numbers are not returned to Slack output.",
    }


@mcp.tool()
def check_eazybe_send_status(
    run_id: str,
    statuses: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize Eazybe send statuses for a daily nurture run."""

    supplied = _status_by_message_id(statuses)
    if not supplied and not _status_api_url():
        return _blocked(
            f"No statuses supplied and {EAZYBE_STATUS_API_URL_ENV} is not configured.",
            _scope(run_id),
        )
    # V1 avoids guessing undocumented provider status query contracts. The
    # scheduled runtime should pass accepted/queued results from the send tool
    # or a dedicated provider poller into this checker.
    counts = {
        "sent": sum(1 for item in supplied.values() if str(item.get("status") or "").lower() in SENT_STATUSES),
        "failed": sum(1 for item in supplied.values() if str(item.get("status") or "").lower() in TERMINAL_FAILURE_STATUSES),
        "pending": sum(1 for item in supplied.values() if str(item.get("status") or "").lower() not in SENT_STATUSES | TERMINAL_FAILURE_STATUSES),
    }
    return {
        "answer": {
            "run_id": run_id,
            "statuses": _redact_phone(list(supplied.values())),
            "counts": counts,
            "sent_definition": "accepted, queued, sent, or delivered",
        },
        "source": "Eazybe send status summary",
        "scope": _scope(run_id),
        "confidence": "needs-check" if counts["pending"] else "verified",
        "caveat": "HubSpot matching WhatsApp communications after run start can also satisfy the 12pm sent definition outside this adapter.",
    }


@mcp.tool()
def build_daily_nurture_reminder(
    run_id: str,
    messages: list[dict[str, Any]] | None = None,
    statuses: list[dict[str, Any]] | dict[str, Any] | None = None,
    ae_slack_user_id: str = "",
    manager_slack_user_id: str = "",
    reminder_channel_id: str = "",
) -> dict[str, Any]:
    """Build the 12pm Slack reminder payload for unsent/unskipped nurture messages."""

    supplied_messages = [message for message in messages or [] if isinstance(message, dict)]
    loaded_from_persisted_run = False
    if not supplied_messages:
        supplied_messages = _load_run_messages(run_id)
        loaded_from_persisted_run = bool(supplied_messages)
    if not supplied_messages:
        return _blocked(
            f"No messages supplied and no persisted daily nurture run found for run_id {run_id}.",
            _scope(run_id, {"reminder_channel_id": reminder_channel_id}),
        )

    text, unsent = _build_reminder_text(run_id, supplied_messages, statuses, ae_slack_user_id, manager_slack_user_id)
    return {
        "answer": {
            "run_id": run_id,
            "loaded_from_persisted_run": loaded_from_persisted_run,
            "should_send_reminder": bool(unsent),
            "reminder_channel_id": reminder_channel_id,
            "slack_text": _redact_phone(text),
            "unsent_message_ids": [message.get("message_id") for message in unsent],
            "unsent_count": len(unsent),
            "tagged_users": [user_id for user_id in [ae_slack_user_id, manager_slack_user_id] if user_id],
        },
        "source": "NurtureAny daily nurture 12pm reminder check",
        "scope": _scope(run_id, {"reminder_channel_id": reminder_channel_id}),
        "confidence": "verified",
        "caveat": "Post this Slack text only when should_send_reminder=true. Sent means Eazybe accepted/queued or HubSpot later shows a matching WhatsApp communication after run start.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
