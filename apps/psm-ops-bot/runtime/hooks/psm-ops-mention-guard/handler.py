"""Hermes gateway hook that detects PSM Ops Bot Slack-mention scope violations.

The bot's prompt (SOUL.md / SKILL.md) forbids `<@U...>`-mentioning anyone other
than the current Slack tagger in thread replies. This hook scans every
`agent:end` response against that rule and posts a one-line audit warning to the
configured central Slack channel when it slips.

It does NOT mutate the response (Hermes hooks are observers here) and does NOT
write to disk — the bad message has already been posted by the time this fires.
The point is purely to give the team a real-time signal in Slack so prompt-rule
regressions are visible immediately rather than silently piling up.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


SLACK_MENTION_RE = re.compile(r"<@([UW][A-Z0-9]{2,})(?:\|[^>]*)?>")
CRON_PREFIX = "PSM Ops automation:"
SILENT_CRON_PREFIX = "[SILENT] PSM Ops automation:"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bot_user_id() -> str:
    return _env("PSM_OPS_BOT_USER_ID").upper()


def _central_channel() -> str:
    # No SLACK_HOME_CHANNEL fallback: unset = no alert, not customer-channel leak.
    return _env("PSM_OPS_CENTRAL_SLACK_CHANNEL_ID")


def _bot_token() -> str:
    return _env("SLACK_BOT_TOKEN") or _env("PSM_OPS_SLACK_BOT_TOKEN")


def _normalize_id(value: Any) -> str:
    return str(value or "").strip().upper()


def _is_cron_output(response: str) -> bool:
    stripped = (response or "").lstrip()
    return stripped.startswith(CRON_PREFIX) or stripped.startswith(SILENT_CRON_PREFIX)


def _coerce_text(response: Any) -> str:
    """Normalize response to text: strings pass through; dicts surface `slack_reply`/`answer`/`text` if present; else JSON dump."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        for key in ("slack_reply", "answer", "text"):
            candidate = response.get(key)
            if isinstance(candidate, str):
                return candidate
    return json.dumps(response, ensure_ascii=False)


def scan_response(response: Any, sender_user_id: str, bot_user_id: str = "") -> list[str]:
    """Return mentions present in `response` that are neither the tagger nor the bot."""

    text = _coerce_text(response)
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
    text = _coerce_text(response)
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
    _post_audit_warning(verdict)
