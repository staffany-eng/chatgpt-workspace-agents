#!/usr/bin/env python3
"""No-agent Launchbot monitor for feature-intake candidates in configured Slack channels."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PROFILE_DIR = Path(os.path.expanduser(os.environ.get("HERMES_PROFILE_DIR") or os.environ.get("HERMES_HOME") or "~/.hermes/profiles/launchbot"))
MCP_DIR_CANDIDATES = [
    SCRIPT_DIR / "mcp",
    SCRIPT_DIR.parent / "runtime" / "mcp",
    PROFILE_DIR / "source" / "launchbot" / "runtime" / "mcp",
]
for mcp_dir in MCP_DIR_CANDIDATES:
    if (mcp_dir / "launchbot_feature_intake_core.py").exists() and str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))
        break

import launchbot_feature_intake_core as intake_core  # noqa: E402


DEFAULT_CHANNELS = ["CF8PK6V4J"]
DEFAULT_STATE_PATH = "~/.hermes/profiles/launchbot/runtime/feature-intake-monitor-state.json"
DEFAULT_MAX_MESSAGES_PER_RUN = 100
DEFAULT_OVERLAP_SECONDS = 600
DEFAULT_SINCE_MINUTES = 15
LAUNCHBOT_AUTOMATION_PREFIX = "launchbot automation:"
ACK_ONLY_RE = re.compile(r"(?i)^\s*(yes|yeah|yup|ok|okay|done|thanks|thank you|\+1|create)\s*[.!]*\s*$")
APPROVAL_RE = re.compile(r"(?i)^\s*(create intake|create ker intake)\s*$")
FEATURE_HINTS = (
    "feature request",
    "feature idea",
    "feature ask",
    "product request",
    "requesting",
    "can we",
    "could we",
    "should we",
    "need to",
    "needs to",
    "we need",
    "would be good",
    "would be useful",
    "automate",
    "automation",
    "build",
    "support",
    "centralized product bot",
)
NOISE_HINTS = (
    LAUNCHBOT_AUTOMATION_PREFIX,
    "gateway shutting down",
    "joined the channel",
    "has left the channel",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def ts_float(value: str | float | int | None, default: float = 0.0) -> float:
    return intake_core.ts_float(value, default)


def parse_list(value: str, default: list[str]) -> list[str]:
    values = [item.strip() for item in re.split(r"[\s,]+", value or "") if item.strip()]
    return values or list(default)


def state_path_from_env() -> Path:
    raw = os.environ.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_STATE_PATH", DEFAULT_STATE_PATH)
    return Path(os.path.expanduser(raw))


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "channels": {}, "sources": {}}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"version": 1, "channels": {}, "sources": {}}
    if not isinstance(state, dict):
        return {"version": 1, "channels": {}, "sources": {}}
    state.setdefault("version", 1)
    state.setdefault("channels", {})
    state.setdefault("sources", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def slack_get(method: str, params: dict[str, Any]) -> dict[str, Any]:
    return intake_core.slack_api(method, params)


def slack_post(method: str, body: dict[str, Any]) -> dict[str, Any]:
    data = urllib.parse.urlencode({key: value for key, value in body.items() if value not in (None, "")}).encode("utf-8")
    request = urllib.request.Request(
        urllib.parse.urljoin(intake_core.SLACK_API_BASE_URL, method),
        data=data,
        headers={
            "Authorization": f"Bearer {intake_core.token('SLACK_BOT_TOKEN')}",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "User-Agent": intake_core.USER_AGENT,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=intake_core.SLACK_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise intake_core.LaunchbotFeatureIntakeError(intake_core.safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise intake_core.LaunchbotFeatureIntakeError(intake_core.safe_error(f"Slack API request failed: {reason}")) from error
    if not payload.get("ok"):
        raise intake_core.LaunchbotFeatureIntakeError(intake_core.safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def message_text(message: dict[str, Any]) -> str:
    return str(message.get("text") or "")


def is_bot_message(message: dict[str, Any]) -> bool:
    return bool(message.get("bot_id") or message.get("subtype") == "bot_message")


def is_launchbot_automation_text(text: str) -> bool:
    return intake_core.safe_text(text).lower().startswith(LAUNCHBOT_AUTOMATION_PREFIX)


def should_skip_message(message: dict[str, Any]) -> bool:
    text = message_text(message)
    safe = intake_core.safe_text(text)
    lowered = safe.lower()
    if not safe:
        return True
    if is_bot_message(message):
        return True
    if message.get("subtype") in {"message_deleted", "channel_join", "channel_leave"}:
        return True
    return any(hint in lowered for hint in NOISE_HINTS)


def is_candidate_text(text: str) -> bool:
    safe = intake_core.safe_text(text)
    lowered = safe.lower()
    if len(safe) < 18 or ACK_ONLY_RE.match(safe):
        return False
    if is_launchbot_automation_text(safe):
        return False
    if intake_core.is_launchbot_intake_automation(safe):
        return True
    hits = sum(1 for hint in FEATURE_HINTS if hint in lowered)
    has_productish_context = any(term in lowered for term in ("feature", "product", "jira", "ker", "request", "customer", "user", "admin", "manager", "automation", "automate"))
    return hits >= 2 or (hits >= 1 and has_productish_context)


def source_url(channel_id: str, thread_ts: str, message_ts: str) -> str:
    return intake_core.source_permalink(channel_id, thread_ts, message_ts, "")


def preview_text(answer: dict[str, Any]) -> str:
    duplicate = answer.get("duplicate")
    if duplicate:
        return (
            "Launchbot automation: Existing KER intake found. "
            f"<{duplicate['url']}|{duplicate['issue_key']}> - {duplicate['summary']}"
        )
    return (
        "Launchbot automation: Potential KER intake detected.\n"
        f"Summary: {answer.get('summary') or 'Feature request from Slack thread'}\n"
        f"Source: {answer.get('source_permalink') or ''}\n"
        "Reply `create intake` in this thread to create it."
    )


def allowed_approver(user_id: str) -> bool:
    approvers = parse_list(os.environ.get("LAUNCHBOT_FEATURE_INTAKE_APPROVER_USER_IDS", ""), [])
    return not approvers or user_id in set(approvers)


def history_messages(channel_id: str, oldest: float, limit: int) -> list[dict[str, Any]]:
    payload = slack_get(
        "conversations.history",
        {
            "channel": channel_id,
            "oldest": f"{oldest:.6f}" if oldest > 0 else "",
            "limit": limit,
            "inclusive": "true",
        },
    )
    messages = [item for item in payload.get("messages", []) if isinstance(item, dict)]
    return sorted(messages, key=lambda item: ts_float(item.get("ts")))


def thread_messages(channel_id: str, thread_ts: str) -> list[dict[str, Any]]:
    payload = slack_get(
        "conversations.replies",
        {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": intake_core.MAX_THREAD_MESSAGES,
            "inclusive": "true",
        },
    )
    return [item for item in payload.get("messages", []) if isinstance(item, dict)]


def record_source(
    state: dict[str, Any],
    source_permalink: str,
    *,
    channel_id: str,
    thread_ts: str,
    message_ts: str,
    safe_summary: str,
    status: str,
    preview_post_ts: str = "",
    issue_key: str = "",
) -> None:
    sources = state.setdefault("sources", {})
    current = sources.get(source_permalink) or {}
    current.update(
        {
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "message_ts": message_ts,
            "permalink": source_permalink,
            "safe_summary": safe_summary,
            "status": status,
            "preview_post_ts": preview_post_ts or current.get("preview_post_ts", ""),
            "issue_key": issue_key or current.get("issue_key", ""),
            "updated_at": now_iso(),
        }
    )
    current.setdefault("created_at", now_iso())
    sources[source_permalink] = current


def process_candidate(state: dict[str, Any], channel_id: str, message: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    message_ts = str(message.get("ts") or "")
    thread_ts = str(message.get("thread_ts") or message_ts)
    permalink = source_url(channel_id, thread_ts, message_ts)
    if not permalink or permalink in state.get("sources", {}):
        return {"action": "skipped", "reason": "duplicate", "permalink": permalink}

    preview = intake_core.preview_feature_intake_from_slack_thread(channel_id=channel_id, thread_ts=thread_ts, message_ts=message_ts)
    if preview.get("confidence") == "blocked":
        return {"action": "blocked", "permalink": permalink, "reason": preview.get("answer")}

    answer = preview.get("answer") or {}
    summary = str(answer.get("summary") or intake_core.safe_text(message_text(message)))
    status = "duplicate_found" if answer.get("duplicate") else "previewed"
    post_ts = ""
    if not dry_run:
        posted = slack_post(
            "chat.postMessage",
            {
                "channel": channel_id,
                "thread_ts": thread_ts,
                "text": preview_text(answer),
                "unfurl_links": "false",
                "unfurl_media": "false",
            },
        )
        post_ts = str(posted.get("ts") or "")
    duplicate = answer.get("duplicate") or {}
    record_source(
        state,
        permalink,
        channel_id=channel_id,
        thread_ts=thread_ts,
        message_ts=message_ts,
        safe_summary=intake_core.safe_text(summary),
        status=status,
        preview_post_ts=post_ts,
        issue_key=str(duplicate.get("issue_key") or ""),
    )
    return {"action": status, "permalink": permalink, "dry_run": dry_run}


def find_approval(messages: list[dict[str, Any]]) -> dict[str, Any] | None:
    for message in sorted(messages, key=lambda item: ts_float(item.get("ts"))):
        if should_skip_message(message):
            continue
        safe = intake_core.safe_text(message_text(message))
        if APPROVAL_RE.match(safe) and allowed_approver(str(message.get("user") or "")):
            return message
    return None


def process_approval(state: dict[str, Any], source: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    channel_id = str(source.get("channel_id") or "")
    thread_ts = str(source.get("thread_ts") or "")
    message_ts = str(source.get("message_ts") or thread_ts)
    permalink = str(source.get("permalink") or source_url(channel_id, thread_ts, message_ts))
    if not channel_id or not thread_ts:
        return {"action": "skipped", "reason": "missing-thread", "permalink": permalink}

    messages = thread_messages(channel_id, thread_ts)
    approval = find_approval(messages)
    if not approval:
        return {"action": "skipped", "reason": "no-approval", "permalink": permalink}
    if dry_run:
        return {"action": "would_create", "permalink": permalink}

    created = intake_core.create_feature_intake_from_slack_thread(
        channel_id=channel_id,
        thread_ts=thread_ts,
        message_ts=message_ts,
        confirmation=intake_core.safe_text(message_text(approval)).lower(),
    )
    answer = created.get("answer") or {}
    reply = answer.get("slack_reply") if isinstance(answer, dict) else ""
    if reply:
        slack_post(
            "chat.postMessage",
            {
                "channel": channel_id,
                "thread_ts": thread_ts,
                "text": reply,
                "unfurl_links": "false",
                "unfurl_media": "false",
            },
        )
    issue = answer.get("issue") if isinstance(answer, dict) else {}
    source["status"] = "created" if answer.get("created") else "duplicate_found"
    source["issue_key"] = str((issue or {}).get("issue_key") or "")
    source["updated_at"] = now_iso()
    return {"action": source["status"], "permalink": permalink, "issue_key": source["issue_key"]}


def process_channel(state: dict[str, Any], channel_id: str, oldest: float, max_messages: int, dry_run: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    messages = history_messages(channel_id, oldest, max_messages)
    channel_state = state.setdefault("channels", {}).setdefault(channel_id, {})
    for message in messages:
        message_ts = str(message.get("ts") or "")
        if message_ts and ts_float(message_ts) > ts_float(channel_state.get("last_seen_ts")):
            channel_state["last_seen_ts"] = message_ts
        if should_skip_message(message):
            continue
        if is_candidate_text(message_text(message)):
            actions.append(process_candidate(state, channel_id, message, dry_run))
    channel_state["updated_at"] = now_iso()
    return actions


def process_pending_approvals(state: dict[str, Any], dry_run: bool) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for source in list((state.get("sources") or {}).values()):
        if source.get("status") != "previewed":
            continue
        actions.append(process_approval(state, source, dry_run))
    return actions


def run_monitor(args: argparse.Namespace) -> dict[str, Any]:
    state_path = Path(os.path.expanduser(args.state_path)) if args.state_path else state_path_from_env()
    state = load_state(state_path)
    channels = parse_list(",".join(args.channel or []), parse_list(os.environ.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_CHANNEL_IDS", ""), DEFAULT_CHANNELS))
    max_messages = int(os.environ.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_MAX_MESSAGES_PER_RUN", args.max_messages))
    overlap_seconds = int(os.environ.get("LAUNCHBOT_FEATURE_INTAKE_MONITOR_OVERLAP_SECONDS", args.overlap_seconds))
    since_cutoff = time.time() - (args.since_minutes * 60)
    actions: list[dict[str, Any]] = []

    for channel_id in channels:
        channel_state = state.setdefault("channels", {}).setdefault(channel_id, {})
        last_seen = ts_float(channel_state.get("last_seen_ts"), 0.0)
        oldest = max(0.0, last_seen - overlap_seconds) if last_seen > 0 else since_cutoff
        actions.extend(process_channel(state, channel_id, oldest, max_messages, args.dry_run))
    actions.extend(process_pending_approvals(state, args.dry_run))

    if not args.dry_run:
        save_state(state_path, state)
    return {
        "dry_run": args.dry_run,
        "channels": channels,
        "state_path": str(state_path),
        "actions": actions,
        "transcript_persisted": False,
        "will_post_message": not args.dry_run,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Monitor configured Slack channels for Launchbot feature intake.")
    parser.add_argument("--dry-run", action="store_true", help="Scan and preview actions without Slack posts, Jira creates, or state writes.")
    parser.add_argument("--channel", action="append", help="Channel ID to monitor. Can be passed multiple times or comma-separated.")
    parser.add_argument("--since-minutes", type=int, default=DEFAULT_SINCE_MINUTES)
    parser.add_argument("--state-path", default="")
    parser.add_argument("--max-messages", type=int, default=DEFAULT_MAX_MESSAGES_PER_RUN)
    parser.add_argument("--overlap-seconds", type=int, default=DEFAULT_OVERLAP_SECONDS)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    result = run_monitor(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
