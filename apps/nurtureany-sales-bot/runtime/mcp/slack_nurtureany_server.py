#!/usr/bin/env python3
"""Read-only Slack context MCP adapter for NurtureAny Sales Bot.

This server reads only bounded context from configured Slack channels so
NurtureAny can route obvious first mentions and summarize selected threads. It
never posts messages, stores transcripts, exports channel history, or uses a user
token.
"""

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

from nurtureany_common.responses import blocked_response


SLACK_API_BASE_URL = "https://slack.com/api/"
SLACK_TIMEOUT_SECONDS = 15
MAX_CONTEXT_MESSAGES = 10
MAX_LOOKBACK_MINUTES = 30
DEFAULT_LOOKBACK_MINUTES = 30
DEFAULT_CONTEXT_LIMIT = 10
MAX_THREAD_CONTEXT_MESSAGES = 50
DEFAULT_THREAD_CONTEXT_LIMIT = 50
USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"


mcp = FastMCP(
    "slack_nurtureany",
    instructions=(
        "Read-only bounded Slack context for NurtureAny quick-intent routing and "
        "selected-thread summaries. Use SLACK_BOT_TOKEN and configured channel "
        "IDs only. Quick intent is max 10 messages or 30 minutes; explicit "
        "thread reads are max 50 messages. Return safe snippets/permalinks only, "
        "and never post or persist raw Slack transcripts."
    ),
)


class SlackIntentError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _scope(channel_id: str, thread_ts: str, limit: int, lookback_minutes: int) -> dict[str, Any]:
    return {
        "channel_id": (channel_id or "").strip(),
        "thread_ts": (thread_ts or "").strip(),
        "requested_limit": limit,
        "lookback_minutes": lookback_minutes,
        "max_context_messages": MAX_CONTEXT_MESSAGES,
        "max_lookback_minutes": MAX_LOOKBACK_MINUTES,
        "read_only": True,
        "transcript_persisted": False,
        "configured_channels_only": True,
    }


def _thread_scope(channel_id: str, thread_ts: str, limit: int, current_ts: str = "") -> dict[str, Any]:
    return {
        "channel_id": (channel_id or "").strip(),
        "thread_ts": (thread_ts or "").strip(),
        "current_ts": (current_ts or "").strip(),
        "requested_limit": limit,
        "max_thread_context_messages": MAX_THREAD_CONTEXT_MESSAGES,
        "read_only": True,
        "transcript_persisted": False,
        "configured_channels_only": True,
    }


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "Slack conversations API", scope)


def _token() -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        raise SlackIntentError("Missing SLACK_BOT_TOKEN.")
    return token


def _configured_channel_ids() -> set[str]:
    raw = (
        os.environ.get("NURTUREANY_SLACK_INTENT_CHANNEL_IDS", "")
        or os.environ.get("SLACK_ALLOWED_CHANNEL_IDS", "")
        or os.environ.get("SLACK_HOME_CHANNEL", "")
    )
    values = re.split(r"[\s,]+", raw.strip())
    return {value for value in values if value}


def _clamp_int(value: int | str | None, default: int, lower: int, upper: int) -> int:
    try:
        parsed = int(value) if value is not None else default
    except (TypeError, ValueError):
        parsed = default
    return max(lower, min(parsed, upper))


def _ts_float(value: str | float | int | None, default: float) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _slack_api(method: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = urllib.parse.urljoin(SLACK_API_BASE_URL, method)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_token()}",
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
        raise SlackIntentError(_safe_slack_error(f"Slack API failed: {error.code} {detail}"), error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise SlackIntentError(f"Slack API request timed out or failed: {reason}") from error

    if not payload.get("ok"):
        error = str(payload.get("error") or "unknown_error")
        raise SlackIntentError(_safe_slack_error(f"Slack API returned error: {error}"))
    return payload


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


def _message_ts(message: dict[str, Any]) -> float:
    return _ts_float(message.get("ts"), 0.0)


def _safe_message(message: dict[str, Any], channel_id: str) -> dict[str, Any]:
    ts = str(message.get("ts") or "")
    permalink = ""
    if ts:
        try:
            payload = _slack_api("chat.getPermalink", {"channel": channel_id, "message_ts": ts})
            permalink = str(payload.get("permalink") or "")
        except SlackIntentError:
            permalink = ""
    return {
        "ts": ts,
        "user_id": str(message.get("user") or message.get("bot_id") or ""),
        "is_bot": bool(message.get("bot_id") or message.get("subtype") == "bot_message"),
        "summary": _safe_text(str(message.get("text") or "")),
        "permalink": permalink,
    }


def _history_messages(channel_id: str, latest: float, oldest: float, limit: int) -> tuple[list[dict[str, Any]], str]:
    payload = _slack_api(
        "conversations.history",
        {
            "channel": channel_id,
            "latest": f"{latest:.6f}",
            "oldest": f"{oldest:.6f}",
            "inclusive": "true",
            "limit": limit,
        },
    )
    return [item for item in payload.get("messages", []) if isinstance(item, dict)], "Slack conversations.history API"


def _thread_messages(
    channel_id: str, thread_ts: str, latest: float, oldest: float, limit: int
) -> tuple[list[dict[str, Any]], str]:
    payload = _slack_api(
        "conversations.replies",
        {
            "channel": channel_id,
            "ts": thread_ts,
            "latest": f"{latest:.6f}",
            "oldest": f"{oldest:.6f}",
            "inclusive": "true",
            "limit": limit,
        },
    )
    messages = [item for item in payload.get("messages", []) if isinstance(item, dict)]
    return [message for message in messages if oldest <= _message_ts(message) <= latest], "Slack conversations.replies API"


def _parse_slack_permalink(permalink: str) -> tuple[str, str]:
    parsed = urllib.parse.urlparse(str(permalink or "").strip())
    match = re.search(r"/archives/([^/]+)/p(\d{10})(\d{6})", parsed.path)
    if not match:
        raise SlackIntentError("Malformed Slack permalink. Expected /archives/<channel>/p<timestamp>.")
    channel_id = urllib.parse.unquote(match.group(1))
    message_ts = f"{match.group(2)}.{match.group(3)}"
    query = urllib.parse.parse_qs(parsed.query)
    thread_ts = str((query.get("thread_ts") or [message_ts])[0] or message_ts)
    return channel_id, thread_ts


def _thread_context(channel_id: str, thread_ts: str, current_ts: str, limit: int) -> dict[str, Any]:
    safe_limit = _clamp_int(limit, DEFAULT_THREAD_CONTEXT_LIMIT, 1, MAX_THREAD_CONTEXT_MESSAGES)
    scope = _thread_scope(channel_id, thread_ts, safe_limit, current_ts)
    channel = (channel_id or "").strip()
    thread = (thread_ts or "").strip()
    configured_channels = _configured_channel_ids()
    if not channel:
        return _blocked("channel_id is required for Slack thread context.", scope)
    if not thread:
        return _blocked("thread_ts is required for Slack thread context.", scope)
    if not configured_channels:
        return _blocked("NURTUREANY_SLACK_INTENT_CHANNEL_IDS or SLACK_HOME_CHANNEL is required.", scope)
    if channel not in configured_channels:
        return _blocked("Slack thread context is restricted to configured channel IDs.", scope)

    latest = max(_ts_float(current_ts, time.time()), _ts_float(thread, 0.0))
    try:
        messages, source = _thread_messages(channel, thread, latest, 0.0, safe_limit)
    except SlackIntentError as error:
        return _blocked(str(error), scope)

    messages = sorted(messages, key=_message_ts)[-safe_limit:]
    safe_messages = [_safe_message(message, channel) for message in messages]
    confidence = "verified" if safe_messages else "needs-check"
    caveat = "Safe snippets/permalinks only; no raw transcript persisted and Slack is not business source of truth."
    return {
        "answer": {
            "messages": safe_messages,
            "safe_summaries": [message.get("summary", "") for message in safe_messages],
            "message_count": len(safe_messages),
            "will_mutate_slack": False,
            "will_post_message": False,
            "transcript_persisted": False,
        },
        "source": source,
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


@mcp.tool()
def read_recent_slack_intent_context(
    channel_id: str,
    thread_ts: str = "",
    current_ts: str = "",
    limit: int = DEFAULT_CONTEXT_LIMIT,
    lookback_minutes: int = DEFAULT_LOOKBACK_MINUTES,
) -> dict[str, Any]:
    """Read bounded recent Slack context for quick-intent routing only."""

    safe_limit = _clamp_int(limit, DEFAULT_CONTEXT_LIMIT, 1, MAX_CONTEXT_MESSAGES)
    safe_lookback = _clamp_int(lookback_minutes, DEFAULT_LOOKBACK_MINUTES, 1, MAX_LOOKBACK_MINUTES)
    scope = _scope(channel_id, thread_ts, safe_limit, safe_lookback)
    channel = (channel_id or "").strip()
    configured_channels = _configured_channel_ids()
    if not channel:
        return _blocked("channel_id is required for Slack intent context.", scope)
    if not configured_channels:
        return _blocked("NURTUREANY_SLACK_INTENT_CHANNEL_IDS or SLACK_HOME_CHANNEL is required.", scope)
    if channel not in configured_channels:
        return _blocked("Slack intent context is restricted to configured channel IDs.", scope)

    latest = _ts_float(current_ts, time.time())
    oldest = latest - (safe_lookback * 60)
    try:
        if thread_ts:
            messages, source = _thread_messages(channel, thread_ts, latest, oldest, safe_limit)
        else:
            messages, source = _history_messages(channel, latest, oldest, safe_limit)
    except SlackIntentError as error:
        return _blocked(str(error), scope)

    messages = sorted(messages, key=_message_ts)[-safe_limit:]
    safe_messages = [_safe_message(message, channel) for message in messages]
    confidence = "verified" if safe_messages else "needs-check"
    caveat = "Safe snippets/permalinks only; no raw transcript persisted and Slack is not business source of truth."
    return {
        "answer": {
            "messages": safe_messages,
            "safe_summaries": [message.get("summary", "") for message in safe_messages],
            "message_count": len(safe_messages),
            "will_mutate_slack": False,
            "will_post_message": False,
            "transcript_persisted": False,
        },
        "source": source,
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


@mcp.tool()
def get_current_slack_thread_context(
    channel_id: str,
    thread_ts: str,
    current_ts: str = "",
    limit: int = DEFAULT_THREAD_CONTEXT_LIMIT,
) -> dict[str, Any]:
    """Read one configured-channel Slack thread after approval or bounded continuation."""

    return _thread_context(channel_id, thread_ts, current_ts, limit)


@mcp.tool()
def get_selected_slack_thread_context(permalink: str, limit: int = DEFAULT_THREAD_CONTEXT_LIMIT) -> dict[str, Any]:
    """Read one configured-channel Slack thread from a user-supplied permalink."""

    try:
        channel_id, thread_ts = _parse_slack_permalink(permalink)
    except SlackIntentError as error:
        safe_limit = _clamp_int(limit, DEFAULT_THREAD_CONTEXT_LIMIT, 1, MAX_THREAD_CONTEXT_MESSAGES)
        return _blocked(str(error), _thread_scope("", "", safe_limit))
    return _thread_context(channel_id, thread_ts, "", limit)


if __name__ == "__main__":
    mcp.run("stdio")
