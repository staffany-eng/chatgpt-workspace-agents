#!/usr/bin/env python3
"""Read-only selected Slack thread context MCP adapter for StaffAny Data Bot."""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

SLACK_API_BASE_URL = "https://slack.com/api/"
SLACK_TIMEOUT_SECONDS = 15
DEFAULT_THREAD_CONTEXT_LIMIT = 20
MAX_THREAD_CONTEXT_MESSAGES = 50
CHANNEL_IDS_ENV = "STAFFANY_DATA_BOT_SLACK_CONTEXT_CHANNEL_IDS"
HOME_CHANNEL_ENV = "SLACK_HOME_CHANNEL"
USER_AGENT = "StaffAny-DataBot/1.0 (+https://staffany.com)"

mcp = FastMCP(
    "staffany_slack_context",
    instructions=(
        "Read-only selected Slack thread context adapter for StaffAny Data Bot. "
        "It uses SLACK_BOT_TOKEN, reads only configured public/source channels, "
        "returns bounded redacted snippets/permalinks, and never posts, searches "
        "workspace history, reacts, pins, or falls back to user tokens."
    ),
)


class StaffAnySlackContextError(RuntimeError):
    pass


def _clamp_int(value: int, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _scope(channel_id: str, thread_ts: str, limit: int, current_ts: str = "") -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "current_ts": current_ts,
        "requested_limit": limit,
        "max_thread_messages": MAX_THREAD_CONTEXT_MESSAGES,
        "configured_channel_ids_env": CHANNEL_IDS_ENV,
        "fallback_channel_ids_env": HOME_CHANNEL_ENV,
        "token_source": "SLACK_BOT_TOKEN",
        "read_only": True,
        "will_post_message": False,
        "will_mutate_slack": False,
        "no_user_token_fallback": True,
        "no_slack_connector_fallback": True,
    }


def _blocked(message: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "Slack bot token selected-thread read",
        "scope": scope,
        "confidence": "blocked",
        "caveat": "No Slack post, workspace search, reaction, pin, or user-token fallback was performed.",
    }


def _token(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StaffAnySlackContextError(f"Missing {name}.")
    return value


def _configured_channel_ids() -> set[str]:
    raw = os.environ.get(CHANNEL_IDS_ENV, "").strip() or os.environ.get(HOME_CHANNEL_ENV, "").strip()
    return {item for item in re.split(r"[\s,]+", raw) if item}


def _safe_slack_error(message: str) -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    safe = str(message).replace(token, "[REDACTED_SLACK_BOT_TOKEN]") if token else str(message)
    return safe[:300]


def _safe_text(value: str) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"<@[^>]+>", "<@user>", text)
    text = re.sub(r"<#[^>]+>", "<#channel>", text)
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[phone]", text)
    text = re.sub(r"\s+", " ", text)
    return text[:220]


def _ts_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _message_ts(message: dict[str, Any]) -> float:
    return _ts_float(str(message.get("ts") or ""), 0.0)


def _slack_api(method: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = urllib.parse.urljoin(SLACK_API_BASE_URL, method)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_token('SLACK_BOT_TOKEN')}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=SLACK_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise StaffAnySlackContextError(_safe_slack_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise StaffAnySlackContextError(_safe_slack_error(f"Slack API request failed: {reason}")) from error

    if not payload.get("ok"):
        raise StaffAnySlackContextError(_safe_slack_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def _parse_slack_permalink(permalink: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(str(permalink or "").strip())
    match = re.search(r"/archives/([^/]+)/p(\d{10})(\d{6})", parsed.path)
    if not match:
        raise StaffAnySlackContextError("Malformed Slack permalink. Expected /archives/<channel>/p<timestamp>.")
    channel_id = urllib.parse.unquote(match.group(1))
    message_ts = f"{match.group(2)}.{match.group(3)}"
    query = urllib.parse.parse_qs(parsed.query)
    thread_ts = str((query.get("thread_ts") or [message_ts])[0] or message_ts)
    return channel_id, thread_ts


def _safe_message(message: dict[str, Any], channel_id: str) -> dict[str, Any]:
    ts = str(message.get("ts") or "")
    permalink = ""
    if ts:
        try:
            payload = _slack_api("chat.getPermalink", {"channel": channel_id, "message_ts": ts})
            permalink = str(payload.get("permalink") or "")
        except StaffAnySlackContextError:
            permalink = ""
    return {
        "ts": ts,
        "user_id": str(message.get("user") or message.get("bot_id") or ""),
        "is_bot": bool(message.get("bot_id") or message.get("subtype") == "bot_message"),
        "summary": _safe_text(str(message.get("text") or "")),
        "permalink": permalink,
    }


def _thread_context(channel_id: str, thread_ts: str, current_ts: str = "", limit: int = DEFAULT_THREAD_CONTEXT_LIMIT) -> dict[str, Any]:
    safe_limit = _clamp_int(limit, DEFAULT_THREAD_CONTEXT_LIMIT, 1, MAX_THREAD_CONTEXT_MESSAGES)
    channel = (channel_id or "").strip()
    thread = (thread_ts or "").strip()
    scope = _scope(channel, thread, safe_limit, current_ts)
    if not channel:
        return _blocked("channel_id is required for Slack thread context.", scope)
    if not thread:
        return _blocked("thread_ts is required for Slack thread context.", scope)
    configured_channels = _configured_channel_ids()
    if channel not in configured_channels:
        if not configured_channels:
            return _blocked(f"{CHANNEL_IDS_ENV} or {HOME_CHANNEL_ENV} is required.", scope)
        return _blocked("Slack selected-thread context is restricted to configured public/source channel IDs.", scope)

    latest = max(_ts_float(current_ts, time.time()), _ts_float(thread, 0.0))
    try:
        payload = _slack_api(
            "conversations.replies",
            {
                "channel": channel,
                "ts": thread,
                "latest": f"{latest:.6f}",
                "oldest": "0",
                "inclusive": "true",
                "limit": safe_limit,
            },
        )
    except StaffAnySlackContextError as error:
        return _blocked(str(error), scope)

    messages = [item for item in payload.get("messages", []) if isinstance(item, dict)]
    messages = sorted(messages, key=_message_ts)[-safe_limit:]
    safe_messages = [_safe_message(message, channel) for message in messages]
    confidence = "verified" if safe_messages else "needs-check"
    return {
        "answer": {
            "messages": safe_messages,
            "safe_summaries": [message.get("summary", "") for message in safe_messages],
            "message_count": len(safe_messages),
            "will_mutate_slack": False,
            "will_post_message": False,
            "will_search_workspace": False,
            "will_add_reaction": False,
            "will_pin_message": False,
            "transcript_persisted": False,
        },
        "source": "Slack conversations.replies API via bot token",
        "scope": scope,
        "confidence": confidence,
        "caveat": "Safe redacted snippets/permalinks only; no raw transcript persisted and Slack is not business source of truth.",
    }


@mcp.tool()
def get_current_slack_thread_context(
    channel_id: str,
    thread_ts: str,
    current_ts: str = "",
    limit: int = DEFAULT_THREAD_CONTEXT_LIMIT,
) -> dict[str, Any]:
    """Read one configured Slack thread by channel_id and thread_ts."""

    return _thread_context(channel_id, thread_ts, current_ts=current_ts, limit=limit)


@mcp.tool()
def get_selected_slack_thread_context(slack_permalink: str, limit: int = DEFAULT_THREAD_CONTEXT_LIMIT) -> dict[str, Any]:
    """Read one configured Slack thread from an explicit StaffAny Slack permalink."""

    safe_limit = _clamp_int(limit, DEFAULT_THREAD_CONTEXT_LIMIT, 1, MAX_THREAD_CONTEXT_MESSAGES)
    try:
        channel_id, thread_ts = _parse_slack_permalink(slack_permalink)
    except StaffAnySlackContextError as error:
        return _blocked(str(error), _scope("", "", safe_limit))
    return _thread_context(channel_id, thread_ts, limit=safe_limit)


if __name__ == "__main__":
    mcp.run()
