#!/usr/bin/env python3
"""Bot-owned Slack audit delivery for PSM Ops Bot."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_CENTRAL_CHANNEL = "#ps-weeman-bot-test"
DEFAULT_MAX_MESSAGE_CHARS = 3800
DEFAULT_SECTION_CHARS = 900


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _truthy(value: str, default: bool = False) -> bool:
    raw = (value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on"}


def _bot_token() -> str:
    return _env("SLACK_BOT_TOKEN")


def _central_channel() -> str:
    return (
        _env("PSM_OPS_CENTRAL_SLACK_CHANNEL_ID")
        or _env("SLACK_HOME_CHANNEL")
        or _env("PSM_OPS_CENTRAL_SLACK_CHANNEL")
        or _env("PSM_OPS_CENTRAL_SLACK_CHANNEL_NAME")
        or DEFAULT_CENTRAL_CHANNEL
    )


def _max_message_chars() -> int:
    try:
        value = int(_env("PSM_OPS_CENTRAL_COPY_MAX_CHARS", str(DEFAULT_MAX_MESSAGE_CHARS)))
    except ValueError:
        return DEFAULT_MAX_MESSAGE_CHARS
    return max(1200, min(value, 12000))


SECRET_PATTERNS = [
    re.compile(r"\b(xox[baprs]-[A-Za-z0-9-]+)\b"),
    re.compile(r"\b(xapp-[A-Za-z0-9-]+)\b"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{12,})\b"),
    re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{10,}"),
    re.compile(r"(?i)(['\"]?[A-Z0-9_]*(?:TOKEN|SECRET|PASSWORD|API_KEY)[A-Z0-9_]*['\"]?\s*[:=]\s*)['\"]?[^'\"\s,}]+['\"]?"),
]


def redact_text(value: Any) -> str:
    text = "" if value is None else str(value)
    for pattern in SECRET_PATTERNS:
        if "(?:TOKEN|SECRET|PASSWORD|API_KEY)" in pattern.pattern:
            text = pattern.sub(lambda match: f"{match.group(1)}[redacted]", text)
        else:
            text = pattern.sub("[redacted]", text)
    return text


def _truncate(text: str, limit: int) -> str:
    safe = redact_text(text)
    if len(safe) <= limit:
        return safe
    return safe[: max(0, limit - 48)].rstrip() + "\n...[truncated for Slack audit copy]"


def _json_block(value: Any, limit: int = DEFAULT_SECTION_CHARS) -> str:
    try:
        text = json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True, default=str)
    except TypeError:
        text = str(value)
    return f"```{_truncate(text, limit)}```"


def _line(label: str, value: Any) -> str:
    text = redact_text(value).strip()
    return f"{label}: {text}" if text else ""


def parse_slack_permalink(url: str) -> dict[str, str]:
    raw = (url or "").strip()
    if not raw:
        return {}
    parsed = urllib.parse.urlparse(raw)
    parts = [part for part in parsed.path.split("/") if part]
    try:
        channel_index = parts.index("archives") + 1
        channel_id = parts[channel_index]
    except (ValueError, IndexError):
        return {}
    query = urllib.parse.parse_qs(parsed.query)
    thread_ts = (query.get("thread_ts") or [""])[0]
    message_part = next((part for part in parts if part.startswith("p") and part[1:].isdigit()), "")
    message_ts = ""
    if message_part:
        digits = message_part[1:]
        if len(digits) > 10:
            message_ts = f"{digits[:10]}.{digits[10:]}"
    return {
        "channel_id": channel_id,
        "message_ts": message_ts,
        "thread_ts": thread_ts or message_ts,
    }


def _slack_get(method: str, params: dict[str, str]) -> dict[str, Any]:
    token = _bot_token()
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured.")
    query = urllib.parse.urlencode(params)
    request = urllib.request.Request(
        f"https://slack.com/api/{method}?{query}",
        headers={"Authorization": f"Bearer {token}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Slack API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Slack API unavailable: {error.reason}") from error
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API failed: {payload.get('error', 'unknown_error')}")
    return payload


def _slack_post(method: str, body: dict[str, Any]) -> dict[str, Any]:
    token = _bot_token()
    if not token:
        raise RuntimeError("SLACK_BOT_TOKEN is not configured.")
    request = urllib.request.Request(
        f"https://slack.com/api/{method}",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"Slack API failed: HTTP {error.code} {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Slack API unavailable: {error.reason}") from error
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API failed: {payload.get('error', 'unknown_error')}")
    return payload


def fetch_slack_thread_transcript(slack_thread_url: str, limit: int = 20) -> dict[str, Any]:
    parsed = parse_slack_permalink(slack_thread_url)
    if not parsed.get("channel_id") or not parsed.get("thread_ts"):
        return {"status": "blocked", "reason": "Unable to parse Slack thread permalink."}
    try:
        payload = _slack_get(
            "conversations.replies",
            {
                "channel": parsed["channel_id"],
                "ts": parsed["thread_ts"],
                "limit": str(max(1, min(int(limit or 20), 50))),
                "inclusive": "true",
            },
        )
    except Exception as error:  # noqa: BLE001 - audit copy must not block Jira/C360.
        return {"status": "blocked", "reason": str(error)}
    messages = payload.get("messages") if isinstance(payload, dict) else []
    lines: list[str] = []
    for message in messages if isinstance(messages, list) else []:
        if not isinstance(message, dict):
            continue
        ts = str(message.get("ts") or "")
        user = str(message.get("user") or message.get("bot_id") or "unknown")
        text = str(message.get("text") or "").replace("\n", " ").strip()
        if text:
            lines.append(f"[{ts}] {user}: {text}")
    return {
        "status": "verified",
        "message_count": len(lines),
        "transcript": "\n".join(lines) if lines else "(no text messages returned)",
    }


def _metrics_path() -> Path | None:
    configured = _env("PSM_OPS_ADOPTION_METRICS_PATH")
    if configured:
        return Path(configured).expanduser()
    if not _truthy(_env("PSM_OPS_ADOPTION_METRICS_ENABLED"), default=False):
        return None
    profile_home = Path(_env("HERMES_HOME") or Path.home() / ".hermes" / "profiles" / "psmopsbot")
    return profile_home / "metrics" / "psm-ops-adoption.jsonl"


def record_adoption_event(event_type: str, fields: dict[str, Any] | None = None) -> None:
    path = _metrics_path()
    if path is None:
        return
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **(fields or {}),
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=True, default=str) + "\n")
    except OSError:
        return


def build_ps_wee_audit_text(
    event_type: str,
    *,
    source_thread_url: str = "",
    issue_key: str = "",
    issue_url: str = "",
    requester: str = "",
    customer: str = "",
    summary: str = "",
    status: str = "",
    missing_info: list[str] | None = None,
    jira_payload: Any = None,
    c360_payload: Any = None,
    blocked_reason: str = "",
    transcript: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    title = f"PSM Ops automation: PS WEE audit - {event_type}"
    lines = [title]
    if source_thread_url:
        lines.append(f"Source thread: {source_thread_url}")
    if issue_key or issue_url:
        jira_ref = f"<{issue_url}|{issue_key}>" if issue_key and issue_url else issue_key or issue_url
        lines.append(f"Jira: {jira_ref}")
    for line in [
        _line("Requester", requester),
        _line("Customer", customer),
        _line("Status", status),
        _line("Summary", summary),
        _line("Blocked reason", blocked_reason),
    ]:
        if line:
            lines.append(line)
    if missing_info:
        lines.append(f"Missing info: {', '.join(redact_text(item) for item in missing_info if str(item).strip())}")
    if transcript is not None:
        lines.append(f"Transcript fetch: {transcript.get('status', 'unknown')}")
        if transcript.get("reason"):
            lines.append(f"Transcript fetch reason: {redact_text(transcript.get('reason'))}")
        if transcript.get("transcript"):
            lines.append("Slack transcript excerpt:")
            lines.append(f"```{_truncate(str(transcript.get('transcript')), DEFAULT_SECTION_CHARS)}```")
    if jira_payload is not None:
        lines.append("Jira payload:")
        lines.append(_json_block(jira_payload))
    if c360_payload is not None:
        lines.append("C360 payload:")
        lines.append(_json_block(c360_payload))
    if extra:
        lines.append("Extra:")
        lines.append(_json_block(extra))
    return _truncate("\n".join(lines), _max_message_chars())


def post_ps_wee_audit(
    event_type: str,
    *,
    source_thread_url: str = "",
    issue_key: str = "",
    issue_url: str = "",
    requester: str = "",
    customer: str = "",
    summary: str = "",
    status: str = "",
    missing_info: list[str] | None = None,
    jira_payload: Any = None,
    c360_payload: Any = None,
    blocked_reason: str = "",
    extra: dict[str, Any] | None = None,
    fetch_thread: bool | None = None,
) -> dict[str, Any]:
    if _truthy(_env("PSM_OPS_CENTRAL_COPY_DISABLED"), default=False):
        return {"ok": False, "skipped": True, "reason": "central copy disabled"}
    channel = _central_channel()
    token = _bot_token()
    if not channel or not token:
        result = {"ok": False, "skipped": True, "reason": "missing Slack bot token or central channel"}
        record_adoption_event(event_type, {**(extra or {}), "central_copy_ok": False, "central_copy_reason": result["reason"]})
        return result
    should_fetch = _truthy(_env("PSM_OPS_CENTRAL_FETCH_SLACK_THREAD"), default=True) if fetch_thread is None else bool(fetch_thread)
    transcript = None
    if should_fetch and source_thread_url:
        transcript = fetch_slack_thread_transcript(source_thread_url)
    text = build_ps_wee_audit_text(
        event_type,
        source_thread_url=source_thread_url,
        issue_key=issue_key,
        issue_url=issue_url,
        requester=requester,
        customer=customer,
        summary=summary,
        status=status,
        missing_info=missing_info,
        jira_payload=jira_payload,
        c360_payload=c360_payload,
        blocked_reason=blocked_reason,
        transcript=transcript,
        extra=extra,
    )
    try:
        payload = _slack_post("chat.postMessage", {"channel": channel, "text": text})
        result = {
            "ok": True,
            "channel": payload.get("channel", channel),
            "ts": payload.get("ts", ""),
            "transcript_fetch": transcript.get("status") if isinstance(transcript, dict) else "skipped",
        }
    except Exception as error:  # noqa: BLE001 - central copy must not break primary action.
        result = {"ok": False, "skipped": False, "reason": str(error)}
    record_adoption_event(
        event_type,
        {
            **(extra or {}),
            "central_copy_ok": bool(result.get("ok")),
            "central_copy_reason": result.get("reason", ""),
            "source_thread_url": source_thread_url,
            "issue_key": issue_key,
            "customer": customer,
            "blocked": bool(blocked_reason),
        },
    )
    return result
