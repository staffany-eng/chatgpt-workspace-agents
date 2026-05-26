"""Hermes gateway hook that detects PSM Ops Bot Slack-mention scope violations.

The bot's prompt (SOUL.md / SKILL.md) forbids `<@U...>`-mentioning anyone other
than the current Slack tagger in thread replies. This hook deterministically
checks every `agent:end` response against that rule, records violations to a
JSONL log, and posts a one-line audit warning to the configured central channel.

It does not mutate the response (Hermes hooks are observers here); it gives the
team a deterministic signal whenever the prompt rule slips through.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SLACK_MENTION_RE = re.compile(r"<@([UW][A-Z0-9]{2,})(?:\|[^>]*)?>")
CRON_PREFIX = "PSM Ops automation:"
SILENT_CRON_PREFIX = "[SILENT] PSM Ops automation:"
DEFAULT_VIOLATIONS_FILENAME = "psm-ops-mention-violations.jsonl"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _violations_path() -> Path:
    configured = _env("PSM_OPS_MENTION_VIOLATIONS_PATH")
    if configured:
        return Path(configured).expanduser()
    profile_home = Path(_env("HERMES_HOME") or Path.home() / ".hermes" / "profiles" / "psmopsbot")
    return profile_home / "metrics" / DEFAULT_VIOLATIONS_FILENAME


def _bot_user_id() -> str:
    return _env("PSM_OPS_BOT_USER_ID").upper()


def _central_channel() -> str:
    return _env("PSM_OPS_CENTRAL_SLACK_CHANNEL_ID") or _env("SLACK_HOME_CHANNEL")


def _bot_token() -> str:
    return _env("SLACK_BOT_TOKEN") or _env("PSM_OPS_SLACK_BOT_TOKEN")


def _normalize_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_cron_output(response: str) -> bool:
    stripped = (response or "").lstrip()
    return stripped.startswith(CRON_PREFIX) or stripped.startswith(SILENT_CRON_PREFIX)


def scan_response(response: Any, sender_user_id: str, bot_user_id: str = "") -> list[str]:
    """Return mentions present in `response` that are neither the tagger nor the bot."""

    text = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
    sender = _normalize_id(sender_user_id)
    bot = _normalize_id(bot_user_id)
    allowed: set[str] = set()
    if sender:
        allowed.add(sender)
    if bot:
        allowed.add(bot)
    found: list[str] = []
    seen: set[str] = set()
    for match in SLACK_MENTION_RE.finditer(text):
        mention_id = match.group(1).upper()
        if mention_id in allowed or mention_id in seen:
            continue
        seen.add(mention_id)
        found.append(mention_id)
    return found


def evaluate(context: dict[str, Any]) -> dict[str, Any]:
    """Pure decision function: returns the verdict without performing IO.

    Result shape:
        {
          "skipped": bool,
          "skip_reason": str,
          "violations": [<user_id>, ...],
          "sender": <user_id>,
          "response_preview": <truncated str>,
        }
    """

    response = context.get("response") if isinstance(context, dict) else None
    text = response if isinstance(response, str) else ("" if response is None else str(response))
    if not text.strip():
        return {"skipped": True, "skip_reason": "empty_response", "violations": [], "sender": "", "response_preview": ""}
    if _is_cron_output(text):
        return {"skipped": True, "skip_reason": "cron_output", "violations": [], "sender": "", "response_preview": ""}
    platform = str((context or {}).get("platform") or "").lower()
    if platform and platform != "slack":
        return {"skipped": True, "skip_reason": f"non_slack_platform:{platform}", "violations": [], "sender": "", "response_preview": ""}
    sender = _normalize_id((context or {}).get("user_id"))
    if not sender:
        # Without a known sender we cannot decide; record as skip so we don't
        # spam the audit channel for cron contexts that lack a Slack user.
        return {"skipped": True, "skip_reason": "missing_sender", "violations": [], "sender": "", "response_preview": _preview(text)}
    violations = scan_response(text, sender, _bot_user_id())
    return {
        "skipped": False,
        "skip_reason": "",
        "violations": violations,
        "sender": sender,
        "response_preview": _preview(text),
    }


def _preview(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\n", " ").strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 20)].rstrip() + " ...[truncated]"


def _record_violation(verdict: dict[str, Any], context: dict[str, Any]) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": context.get("session_id", ""),
        "session_key": context.get("session_key", ""),
        "sender_user_id": verdict.get("sender", ""),
        "violating_user_ids": verdict.get("violations", []),
        "response_preview": verdict.get("response_preview", ""),
    }
    path = _violations_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle_file:
            handle_file.write(json.dumps(entry, ensure_ascii=True, default=str) + "\n")
    except OSError:
        pass


def _post_audit_warning(verdict: dict[str, Any]) -> None:
    channel = _central_channel()
    token = _bot_token()
    if not channel or not token:
        return
    sender = verdict.get("sender") or "unknown"
    violating = " ".join(f"<@{uid}>" for uid in verdict.get("violations") or [])
    text = (
        "PSM Ops mention-guard: bot reply contained non-tagger mention(s) "
        f"{violating} but the current Slack tagger was <@{sender}>. "
        "See SOUL.md `Slack Output` rule."
    )
    body = json.dumps({"channel": channel, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=10).read()
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        # Best-effort: never let the audit alert raise into the agent loop.
        return


async def handle(event_type: str, context: dict[str, Any]):
    if event_type != "agent:end":
        return
    verdict = evaluate(context or {})
    if verdict["skipped"] or not verdict["violations"]:
        return
    _record_violation(verdict, context or {})
    _post_audit_warning(verdict)
