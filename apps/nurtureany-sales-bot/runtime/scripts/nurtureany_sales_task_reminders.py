#!/usr/bin/env python3
"""Deterministic HubSpot task reminder digest for Hermes no-agent cron."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_CALLER_EMAIL = "kaiyi@staffany.com"
AUTOMATION_PREFIX = "NurtureAny automation:"
HERMES_VENV_REEXEC_ENV = "_NURTUREANY_TASK_REMINDER_HERMES_VENV"


class ReminderError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _profile_dir() -> Path:
    configured = _env("HERMES_PROFILE_DIR") or _env("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".hermes" / "profiles" / "nurtureanysalesbot"


def ensure_runtime_python() -> None:
    """Use the Hermes venv when cron invokes the script through /usr/bin/env python3."""

    if os.environ.get(HERMES_VENV_REEXEC_ENV):
        return
    hermes_home = _profile_dir().parents[1]
    venv_python = hermes_home / "hermes-agent" / "venv" / "bin" / "python"
    if not venv_python.exists():
        return
    current = Path(sys.executable)
    if current == venv_python:
        return
    os.environ[HERMES_VENV_REEXEC_ENV] = "1"
    os.execv(str(venv_python), [str(venv_python), *sys.argv])


def load_profile_env() -> None:
    """Load profile .env values when Hermes does not inject them into no-agent jobs."""

    env_path = _profile_dir() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def _runtime_root() -> Path:
    current = Path(__file__).resolve()
    repo_runtime = current.parents[1]
    if (repo_runtime / "mcp").exists():
        return repo_runtime
    profile_runtime = _profile_dir() / "runtime"
    if (profile_runtime / "mcp").exists():
        return profile_runtime
    return repo_runtime


def _load_hubspot_module():
    mcp_dir = _runtime_root() / "mcp"
    if str(mcp_dir) not in sys.path:
        sys.path.insert(0, str(mcp_dir))
    import hubspot_nurtureany_server

    return hubspot_nurtureany_server


def _timezone() -> ZoneInfo:
    timezone_name = _env("NURTUREANY_TASK_REMINDER_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ReminderError("NURTUREANY_TASK_REMINDER_TIMEZONE must be a valid IANA timezone.") from error


def _default_mode(argv0: str) -> str:
    return "eod" if "eod" in Path(argv0).stem.lower() else "morning"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe NurtureAny HubSpot task reminder digest.")
    parser.add_argument("--mode", choices=["morning", "eod"], default=_default_mode(sys.argv[0]))
    parser.add_argument("--as-of", default="", help="ISO date/timestamp. Defaults to now in Asia/Singapore.")
    parser.add_argument("--caller-email", default=_env("NURTUREANY_TASK_REMINDER_CALLER_EMAIL", DEFAULT_CALLER_EMAIL))
    parser.add_argument("--max-results", type=int, default=int(_env("NURTUREANY_TASK_REMINDER_MAX_RESULTS", "100") or "100"))
    parser.add_argument("--dry-run", action="store_true", help="Mark output as dry-run. No writes are ever performed.")
    return parser.parse_args(argv)


def _parse_as_of(value: str, local_timezone: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(local_timezone)
    raw = value.strip()
    if len(raw) == 10:
        return datetime.combine(date.fromisoformat(raw), datetime.min.time(), tzinfo=local_timezone)
    parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(local_timezone)


def _task_line(task: dict[str, Any]) -> str:
    company = str(task.get("company_name") or task.get("company_id") or "Unknown account")
    subject = str(task.get("subject") or "Untitled task")
    due_at = str(task.get("due_at") or "No due date")
    owner = str(task.get("owner_email") or task.get("owner_id") or "Unknown owner")
    task_id = str(task.get("task_id") or "")
    task_ref = f" | Task: {task_id}" if task_id else ""
    return f"- {company}: {subject} | Due: {due_at} | Owner: {owner}{task_ref}"


def format_digest(result: dict[str, Any], mode: str, as_of: datetime, dry_run: bool = False) -> str:
    if result.get("confidence") == "blocked":
        return "\n".join(
            [
                f"{AUTOMATION_PREFIX} HubSpot task reminder blocked",
                "Source: HubSpot Tasks API",
                "Confidence: blocked",
                f"Caveat: {result.get('caveat') or result.get('answer')}",
            ]
        )

    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    buckets = answer.get("buckets") if isinstance(answer.get("buckets"), dict) else {}
    total = int(answer.get("total_task_count") or 0)
    dry_label = " DRY RUN" if dry_run else ""
    if total == 0:
        return (
            f"{AUTOMATION_PREFIX} no HubSpot task reminders for {as_of.date().isoformat()} "
            f"({mode}; {answer.get('window') or 'due window'}).{dry_label}"
        )

    lines = [
        f"{AUTOMATION_PREFIX} HubSpot task reminder{dry_label} - {as_of.date().isoformat()}",
        f"Mode: {mode}",
        f"Window: {answer.get('window') or 'overdue and due'}",
        "Source: HubSpot Task hs_timestamp; incomplete until hs_task_status=COMPLETED",
        f"Total tasks: {total}",
    ]
    for label, key in [("Overdue", "overdue"), ("Due Today", "due_today"), ("Due Tomorrow", "due_tomorrow")]:
        tasks = buckets.get(key) or []
        if not tasks:
            continue
        lines.append("")
        lines.append(f"{label}:")
        for task in tasks:
            lines.append(_task_line(task))
    if result.get("task_truncated"):
        lines.append("")
        lines.append("Caveat: reminder result was truncated; review HubSpot for the full queue.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_runtime_python()
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        local_timezone = _timezone()
        as_of = _parse_as_of(args.as_of, local_timezone)
        module = _load_hubspot_module()
        result = module.list_due_hubspot_sales_task_reminders(
            slack_user_email=args.caller_email,
            mode=args.mode,
            as_of=as_of.isoformat(),
            limit=args.max_results,
        )
        print(format_digest(result, args.mode, as_of, args.dry_run))
        return 0 if result.get("confidence") != "blocked" else 1
    except Exception as error:
        print(
            "\n".join(
                [
                    f"{AUTOMATION_PREFIX} HubSpot task reminder blocked",
                    "Source: HubSpot Tasks API",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
