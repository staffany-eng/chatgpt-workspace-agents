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
from datetime import date as date_cls
from datetime import datetime, time as datetime_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
DEFAULT_STANDUP_LOOKBACK_DAYS = 30
MAX_STANDUP_LOOKBACK_DAYS = 90
MAX_STANDUP_AUDIT_MESSAGES = 2000
MAX_STANDUP_AUDIT_MEMBERS = 2000
USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
STANDUP_PATTERNS = (
    re.compile(r"\bstand\s*[- ]?up\b", re.IGNORECASE),
    re.compile(r"\bstandup\b", re.IGNORECASE),
    re.compile(r"\bstart\s+of\s+day\b", re.IGNORECASE),
    re.compile(r"\bsod\b", re.IGNORECASE),
)
STANDDOWN_PATTERNS = (
    re.compile(r"\bstand\s*[- ]?down\b", re.IGNORECASE),
    re.compile(r"\bstanddown\b", re.IGNORECASE),
    re.compile(r"\bend\s+of\s+day\b", re.IGNORECASE),
    re.compile(r"\beod\b", re.IGNORECASE),
)


mcp = FastMCP(
    "slack_nurtureany",
    instructions=(
        "Read-only bounded Slack context for NurtureAny quick-intent routing and "
        "selected-thread summaries. Use SLACK_BOT_TOKEN and configured channel "
        "IDs only. Quick intent is max 10 messages or 30 minutes; explicit "
        "thread reads may run before approval for planning context, are max 50 "
        "messages, and may auto-join public source channels when explicitly "
        "enabled. Return safe snippets/permalinks only, and never post or persist "
        "raw Slack transcripts."
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
        "configured_public_channel_auto_join": True,
    }


def _thread_scope(channel_id: str, thread_ts: str, limit: int, current_ts: str = "") -> dict[str, Any]:
    allow_all_public = _allow_all_public_thread_channels()
    return {
        "channel_id": (channel_id or "").strip(),
        "thread_ts": (thread_ts or "").strip(),
        "current_ts": (current_ts or "").strip(),
        "requested_limit": limit,
        "max_thread_context_messages": MAX_THREAD_CONTEXT_MESSAGES,
        "read_only": True,
        "transcript_persisted": False,
        "configured_channels_only": not allow_all_public,
        "allow_all_public_channels": allow_all_public,
        "public_channels_only": True,
    }


def _standup_scope(channel_id: str, audit_date: str, timezone_name: str, roster_lookback_days: int) -> dict[str, Any]:
    return {
        "channel_id": (channel_id or "").strip(),
        "date": (audit_date or "").strip(),
        "timezone": (timezone_name or "").strip(),
        "roster_lookback_days": roster_lookback_days,
        "max_roster_lookback_days": MAX_STANDUP_LOOKBACK_DAYS,
        "max_audit_messages": MAX_STANDUP_AUDIT_MESSAGES,
        "read_only": True,
        "transcript_persisted": False,
        "raw_note_bodies_returned": False,
        "configured_channels_only": True,
        "configured_public_channel_auto_join": True,
    }


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "Slack conversations API", scope)


def _token() -> str:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        raise SlackIntentError("Missing SLACK_BOT_TOKEN.")
    return token


def _channel_ids_from_env(*names: str) -> set[str]:
    raw = ""
    for name in names:
        raw = os.environ.get(name, "").strip()
        if raw:
            break
    values = re.split(r"[\s,]+", raw.strip())
    return {value for value in values if value}


def _configured_channel_ids() -> set[str]:
    return _channel_ids_from_env(
        "NURTUREANY_SLACK_INTENT_CHANNEL_IDS",
        "SLACK_ALLOWED_CHANNEL_IDS",
        "SLACK_HOME_CHANNEL",
    )


def _configured_thread_channel_ids() -> set[str]:
    return _channel_ids_from_env(
        "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS",
        "NURTUREANY_SLACK_INTENT_CHANNEL_IDS",
        "SLACK_ALLOWED_CHANNEL_IDS",
        "SLACK_HOME_CHANNEL",
    )


def _configured_standup_channel_ids() -> set[str]:
    return _channel_ids_from_env("NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS")


def _thread_channel_config_source() -> str:
    if os.environ.get("NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS", "").strip():
        return "NURTUREANY_SLACK_THREAD_CONTEXT_CHANNEL_IDS"
    return "NURTUREANY_SLACK_INTENT_CHANNEL_IDS or SLACK_HOME_CHANNEL"


def _truthy_env(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _allow_all_public_thread_channels() -> bool:
    mode = os.environ.get("NURTUREANY_SLACK_THREAD_CONTEXT_PUBLIC_CHANNELS", "").strip().lower()
    return mode in {"all", "public", "true", "1", "yes", "on"} or _truthy_env(
        "NURTUREANY_SLACK_THREAD_CONTEXT_ALLOW_ALL_PUBLIC"
    )


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


def _message_permalink(channel_id: str, ts: str) -> str:
    if not ts:
        return ""
    try:
        payload = _slack_api("chat.getPermalink", {"channel": channel_id, "message_ts": ts})
    except SlackIntentError:
        return ""
    return str(payload.get("permalink") or "")


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


def _history_messages_paginated(
    channel_id: str,
    latest: float,
    oldest: float,
    max_messages: int = MAX_STANDUP_AUDIT_MESSAGES,
) -> tuple[list[dict[str, Any]], str, bool]:
    messages: list[dict[str, Any]] = []
    cursor = ""
    has_more = False
    while len(messages) < max_messages:
        payload = _slack_api(
            "conversations.history",
            {
                "channel": channel_id,
                "latest": f"{latest:.6f}",
                "oldest": f"{oldest:.6f}",
                "inclusive": "true",
                "limit": min(200, max_messages - len(messages)),
                "cursor": cursor,
            },
        )
        messages.extend(item for item in payload.get("messages", []) if isinstance(item, dict))
        cursor = str(((payload.get("response_metadata") or {}).get("next_cursor") or "")).strip()
        has_more = bool(cursor)
        if not cursor:
            break
    return messages[:max_messages], "Slack conversations.history API", has_more


def _history_messages_paginated_with_public_join(
    channel_id: str,
    latest: float,
    oldest: float,
    max_messages: int = MAX_STANDUP_AUDIT_MESSAGES,
) -> tuple[list[dict[str, Any]], str, bool]:
    try:
        messages, source, truncated = _history_messages_paginated(channel_id, latest, oldest, max_messages)
        return messages, source, truncated
    except SlackIntentError as error:
        if "not_in_channel" not in str(error):
            raise
        _join_public_channel(channel_id)
        messages, source, truncated = _history_messages_paginated(channel_id, latest, oldest, max_messages)
        return messages, f"{source} after Slack conversations.join", truncated


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


def _join_public_channel(channel_id: str) -> None:
    _slack_api("conversations.join", {"channel": channel_id})


def _is_public_channel(channel_id: str) -> bool:
    payload = _slack_api("conversations.info", {"channel": channel_id})
    channel = payload.get("channel") if isinstance(payload, dict) else {}
    if not isinstance(channel, dict):
        return False
    return bool(channel.get("is_channel")) and not bool(channel.get("is_private"))


def _channel_member_ids(channel_id: str) -> tuple[set[str], bool]:
    members: set[str] = set()
    cursor = ""
    has_more = False
    while len(members) < MAX_STANDUP_AUDIT_MEMBERS:
        payload = _slack_api(
            "conversations.members",
            {
                "channel": channel_id,
                "limit": min(200, MAX_STANDUP_AUDIT_MEMBERS - len(members)),
                "cursor": cursor,
            },
        )
        members.update(str(member) for member in payload.get("members", []) if member)
        cursor = str(((payload.get("response_metadata") or {}).get("next_cursor") or "")).strip()
        has_more = bool(cursor)
        if not cursor:
            break
    return members, has_more


def _channel_member_ids_with_public_join(channel_id: str) -> tuple[set[str], bool, bool]:
    try:
        members, truncated = _channel_member_ids(channel_id)
        return members, truncated, False
    except SlackIntentError as error:
        if "not_in_channel" not in str(error):
            raise
        _join_public_channel(channel_id)
        members, truncated = _channel_member_ids(channel_id)
        return members, truncated, True


def _user_profile(user_id: str) -> dict[str, Any]:
    payload = _slack_api("users.info", {"user": user_id})
    user = payload.get("user") if isinstance(payload, dict) else {}
    if not isinstance(user, dict):
        raise SlackIntentError("Slack users.info returned an invalid user payload.")
    profile = user.get("profile") if isinstance(user.get("profile"), dict) else {}
    display_name = (
        profile.get("real_name_normalized")
        or user.get("real_name")
        or profile.get("display_name_normalized")
        or user.get("name")
        or user_id
    )
    title = str(profile.get("title") or "")
    return {
        "user_id": user_id,
        "display_name": str(display_name),
        "title": title,
        "deleted": bool(user.get("deleted")),
        "is_bot": bool(user.get("is_bot")) or bool(user.get("is_app_user")),
        "role": _infer_standup_role(f"{display_name} {title}"),
    }


def _infer_standup_role(text: str) -> str:
    lowered = str(text or "").lower()
    if re.search(r"\b(marketing|mkt|growth|brand|campaign|content)\b", lowered):
        return "marketing"
    if re.search(r"\b(bd\s*ops|business development ops|business development operations|sales ops|revops|revenue ops)\b", lowered):
        return "bd_ops"
    if re.search(r"\b(sales|account executive|ae|business development|bd|revenue)\b", lowered):
        return "sales"
    return "unknown"


def _standup_kind(text: str) -> set[str]:
    value = str(text or "")
    kinds: set[str] = set()
    if any(pattern.search(value) for pattern in STANDUP_PATTERNS):
        kinds.add("standup")
    if any(pattern.search(value) for pattern in STANDDOWN_PATTERNS):
        kinds.add("standdown")
    return kinds


def _parse_audit_window(audit_date: str, timezone_name: str) -> tuple[date_cls, float, float]:
    tz_name = (timezone_name or "Asia/Singapore").strip()
    try:
        tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError as error:
        raise SlackIntentError(f"Unsupported timezone: {tz_name}") from error
    raw_date = (audit_date or "").strip().lower()
    today = datetime.now(tz).date()
    if raw_date in {"", "today"}:
        local_date = today
    else:
        try:
            local_date = date_cls.fromisoformat(raw_date)
        except ValueError as error:
            raise SlackIntentError("date must be YYYY-MM-DD or today.") from error
    if local_date > today:
        raise SlackIntentError("date cannot be in the future; pass today or an explicit past/current local date.")
    start = datetime.combine(local_date, datetime_time.min, tzinfo=tz)
    end = start + timedelta(days=1)
    return local_date, start.astimezone(timezone.utc).timestamp(), end.astimezone(timezone.utc).timestamp()


def _thread_messages_with_public_join(
    channel_id: str, thread_ts: str, latest: float, oldest: float, limit: int
) -> tuple[list[dict[str, Any]], str, bool]:
    try:
        messages, source = _thread_messages(channel_id, thread_ts, latest, oldest, limit)
        return messages, source, False
    except SlackIntentError as error:
        if "not_in_channel" not in str(error):
            raise
        _join_public_channel(channel_id)
        messages, source = _thread_messages(channel_id, thread_ts, latest, oldest, limit)
        return messages, f"{source} after Slack conversations.join", True


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
    configured_channels = _configured_thread_channel_ids()
    allow_all_public = _allow_all_public_thread_channels()
    if not channel:
        return _blocked("channel_id is required for Slack thread context.", scope)
    if not thread:
        return _blocked("thread_ts is required for Slack thread context.", scope)
    if channel not in configured_channels:
        if not allow_all_public:
            if not configured_channels:
                return _blocked(f"{_thread_channel_config_source()} is required.", scope)
            return _blocked("Slack thread context is restricted to configured thread-context channel IDs.", scope)
        try:
            if not _is_public_channel(channel):
                return _blocked("Slack thread context can only auto-join public channels.", scope)
        except SlackIntentError as error:
            return _blocked(str(error), scope)

    latest = max(_ts_float(current_ts, time.time()), _ts_float(thread, 0.0))
    try:
        messages, source, joined_public_channel = _thread_messages_with_public_join(channel, thread, latest, 0.0, safe_limit)
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
            "may_join_configured_public_channel": True,
            "may_join_public_channel": allow_all_public or channel in configured_channels,
            "joined_public_channel": joined_public_channel,
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
    """Read one selected Slack thread for preflight context, approval, or bounded continuation."""

    return _thread_context(channel_id, thread_ts, current_ts, limit)


@mcp.tool()
def get_selected_slack_thread_context(permalink: str, limit: int = DEFAULT_THREAD_CONTEXT_LIMIT) -> dict[str, Any]:
    """Read one selected Slack thread from a user-supplied permalink."""

    try:
        channel_id, thread_ts = _parse_slack_permalink(permalink)
    except SlackIntentError as error:
        safe_limit = _clamp_int(limit, DEFAULT_THREAD_CONTEXT_LIMIT, 1, MAX_THREAD_CONTEXT_MESSAGES)
        return _blocked(str(error), _thread_scope("", "", safe_limit))
    return _thread_context(channel_id, thread_ts, "", limit)


@mcp.tool()
def audit_standup_down_accountability(
    channel_id: str,
    date: str,
    timezone: str = "Asia/Singapore",
    roster_lookback_days: int = DEFAULT_STANDUP_LOOKBACK_DAYS,
) -> dict[str, Any]:
    """Audit one allowed Slack channel for stand-up/down accountability. Pass date="today" for relative today."""

    safe_lookback = _clamp_int(roster_lookback_days, DEFAULT_STANDUP_LOOKBACK_DAYS, 1, MAX_STANDUP_LOOKBACK_DAYS)
    scope = _standup_scope(channel_id, date, timezone, safe_lookback)
    channel = (channel_id or "").strip()
    configured_channels = _configured_standup_channel_ids()
    if not channel:
        return _blocked("channel_id is required for stand-up/down accountability audit.", scope)
    if not configured_channels:
        return _blocked("NURTUREANY_STANDUP_AUDIT_CHANNEL_IDS is required.", scope)
    if channel not in configured_channels:
        return _blocked("Stand-up/down accountability audit is restricted to configured channel IDs.", scope)

    try:
        local_date, start_ts, end_ts = _parse_audit_window(date, timezone)
        if not _is_public_channel(channel):
            return _blocked("Stand-up/down accountability audit supports configured public Slack channels only.", scope)
        active_member_ids, members_truncated, member_joined_public_channel = _channel_member_ids_with_public_join(channel)
        baseline_oldest = start_ts - (safe_lookback * 24 * 60 * 60)
        baseline_messages, baseline_source, baseline_truncated = _history_messages_paginated_with_public_join(
            channel, start_ts, baseline_oldest
        )
        today_messages, today_source, today_truncated = _history_messages_paginated_with_public_join(channel, end_ts, start_ts)
    except SlackIntentError as error:
        return _blocked(str(error), scope)

    baseline_user_ids = {
        str(message.get("user") or "")
        for message in baseline_messages
        if str(message.get("user") or "") and _standup_kind(str(message.get("text") or ""))
    }
    today_hits_by_user: dict[str, dict[str, list[str]]] = {}
    for message in today_messages:
        user_id = str(message.get("user") or "")
        if not user_id:
            continue
        kinds = _standup_kind(str(message.get("text") or ""))
        if not kinds:
            continue
        hit = today_hits_by_user.setdefault(user_id, {"standup": [], "standdown": []})
        ts = str(message.get("ts") or "")
        permalink = _message_permalink(channel, ts)
        for kind in kinds:
            hit[kind].append(permalink or ts)

    candidate_user_ids = sorted(baseline_user_ids & active_member_ids)
    profiles: dict[str, dict[str, Any]] = {}
    try:
        for user_id in candidate_user_ids:
            profile = _user_profile(user_id)
            if profile["deleted"] or profile["is_bot"]:
                continue
            profiles[user_id] = profile
    except SlackIntentError as error:
        return _blocked(str(error), scope)

    rows: list[dict[str, Any]] = []
    status_counts = {"complete": 0, "missing_standup": 0, "missing_standdown": 0, "missing_both": 0}
    for user_id, profile in sorted(profiles.items(), key=lambda item: item[1]["display_name"].lower()):
        hits = today_hits_by_user.get(user_id, {"standup": [], "standdown": []})
        has_standup = bool(hits.get("standup"))
        has_standdown = bool(hits.get("standdown"))
        if has_standup and has_standdown:
            status = "complete"
        elif has_standdown:
            status = "missing_standup"
        elif has_standup:
            status = "missing_standdown"
        else:
            status = "missing_both"
        status_counts[status] += 1
        role = str(profile.get("role") or "unknown")
        rows.append(
            {
                "user_id": user_id,
                "display_name": profile["display_name"],
                "role": role,
                "role_needs_check": role == "unknown",
                "status": status,
                "has_standup": has_standup,
                "has_standdown": has_standdown,
                "standup_permalinks": hits.get("standup", [])[:3],
                "standdown_permalinks": hits.get("standdown", [])[:3],
            }
        )

    expected_user_ids = set(profiles)
    today_participant_ids = set(today_hits_by_user)
    extra_today_participants = sorted(today_participant_ids - expected_user_ids)
    source = today_source if today_source == baseline_source else f"{baseline_source}; {today_source}"
    truncated = bool(members_truncated or baseline_truncated or today_truncated)
    joined_public_channel = member_joined_public_channel or "after Slack conversations.join" in source
    confidence = "verified" if rows and not truncated else "needs-check"
    caveat = (
        "Safe per-person status/permalinks only; no raw note bodies returned. "
        "Active member means Slack channel member, not HR employment truth."
    )
    return {
        "answer": {
            "date": local_date.isoformat(),
            "timezone": timezone,
            "channel_id": channel,
            "expected_people_count": len(rows),
            "complete_count": status_counts["complete"],
            "missing_standup_count": status_counts["missing_standup"] + status_counts["missing_both"],
            "missing_standdown_count": status_counts["missing_standdown"] + status_counts["missing_both"],
            "missing_both_count": status_counts["missing_both"],
            "role_needs_check_count": sum(1 for row in rows if row["role_needs_check"]),
            "rows": rows,
            "extra_today_participant_count": len(extra_today_participants),
            "extra_today_participant_user_ids": extra_today_participants[:20],
            "roster_source": "active Slack channel members intersected with prior stand-up/down participants",
            "will_mutate_slack": False,
            "will_post_message": False,
            "transcript_persisted": False,
            "raw_note_bodies_returned": False,
            "may_join_configured_public_channel": True,
            "joined_public_channel": joined_public_channel,
            "members_truncated": members_truncated,
            "baseline_messages_truncated": baseline_truncated,
            "today_messages_truncated": today_truncated,
        },
        "source": source,
        "scope": scope,
        "confidence": confidence,
        "caveat": caveat,
    }


if __name__ == "__main__":
    mcp.run("stdio")
