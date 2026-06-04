#!/usr/bin/env python3
"""Summarize PSM Ops adoption metrics for Hermes no-agent cron delivery."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _metrics_path() -> Path:
    configured = _env("PSM_OPS_ADOPTION_METRICS_PATH")
    if configured:
        return Path(configured).expanduser()
    profile_home = Path(_env("HERMES_HOME") or Path.home() / ".hermes" / "profiles" / "psmopsbot")
    return profile_home / "metrics" / "psm-ops-adoption.jsonl"


def _days() -> int:
    try:
        return max(1, min(int(_env("PSM_OPS_ADOPTION_DIGEST_DAYS", "7")), 30))
    except ValueError:
        return 7


def _parse_timestamp(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _load_events(path: Path, days: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = _parse_timestamp(str(entry.get("timestamp") or ""))
            if timestamp and timestamp >= cutoff:
                events.append(entry)
    return events


def _top(counter: Counter, limit: int = 5) -> str:
    if not counter:
        return "none"
    return ", ".join(f"{name}={count}" for name, count in counter.most_common(limit))


def main() -> int:
    days = _days()
    path = _metrics_path()
    events = _load_events(path, days)
    if not events:
        print(
            "PSM Ops automation: PS WEE adoption digest\n"
            f"Window: last {days} day(s)\n"
            "Events: 0\n"
            f"Metrics file: {path}\n"
            "No adoption events recorded yet."
        )
        return 0

    event_counts = Counter(str(event.get("event_type") or "unknown") for event in events)
    unique_users = {str(event.get("user_id") or "") for event in events if event.get("user_id")}
    unique_sessions = {str(event.get("session_id") or "") for event in events if event.get("session_id")}
    unique_threads = {str(event.get("source_thread_url") or "") for event in events if event.get("source_thread_url")}
    psm_tools = Counter()
    blockers = Counter()
    central_ok = 0
    central_failed = 0
    for event in events:
        for tool_name in event.get("psm_tool_names") or []:
            psm_tools[str(tool_name)] += 1
        blocked = (
            event.get("blocked")
            or event.get("response_confidence") == "blocked"
            or "blocked" in str(event.get("event_type") or "")
        )
        if blocked:
            reason = str(
                event.get("blocked_reason")
                or event.get("central_copy_reason")
                or event.get("response_preview")
                or "blocked"
            )
            blockers[reason[:120]] += 1
        if "central_copy_ok" in event:
            if event.get("central_copy_ok"):
                central_ok += 1
            else:
                central_failed += 1

    ticket_events = Counter({
        name: event_counts.get(name, 0)
        for name in [
            "ticket_created",
            "ticket_reused",
            "roi_ticket_created",
            "roi_ticket_reused",
            "roi_tracker_linked",
            "ticket_update_synced",
        ]
    })
    c360_events = Counter({
        name: event_counts.get(name, 0)
        for name in ["c360_search", "c360_account_context", "c360_customer_answer", "c360_blocked"]
    })

    lines = [
        "PSM Ops automation: PS WEE adoption digest",
        f"Window: last {days} day(s)",
        f"Events: {len(events)}",
        f"Unique users: {len(unique_users)}",
        f"Unique sessions: {len(unique_sessions)}",
        f"Source threads linked: {len(unique_threads)}",
        f"Ticket lifecycle: {_top(ticket_events)}",
        f"C360 usage: {_top(c360_events)}",
        f"Top PSM tools: {_top(psm_tools)}",
        f"Blocked events: {sum(blockers.values())}",
        f"Top blockers: {_top(blockers, 3)}",
        f"Central copy: ok={central_ok}, failed={central_failed}",
        "Manual Hermes checks: hermes -p psmopsbot insights --days 30 --source slack; hermes -p psmopsbot sessions stats",
    ]
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
