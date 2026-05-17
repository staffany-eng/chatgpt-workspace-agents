#!/usr/bin/env python3
"""Deterministic Sales WhatsApp report runner for Hermes no-agent cron."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any


AUTOMATION_PREFIX = "NurtureAny automation:"
DEFAULT_SCHEDULE_ID = "id-whatsapp-morning-report"
HERMES_VENV_REEXEC_ENV = "_NURTUREANY_SALES_REPORT_HERMES_VENV"


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _profile_dir() -> Path:
    configured_profile = _env("HERMES_PROFILE_DIR")
    if configured_profile:
        return Path(configured_profile).expanduser()
    configured_home = _env("HERMES_HOME")
    if configured_home:
        home_path = Path(configured_home).expanduser()
        if (home_path / ".env").exists():
            return home_path
        profile_path = home_path / "profiles" / "nurtureanysalesbot"
        if profile_path.exists():
            return profile_path
    installed_profile = Path(__file__).resolve().parents[1]
    if (installed_profile / ".env").exists():
        return installed_profile
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


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a persisted Sales WhatsApp report schedule.")
    parser.add_argument("--schedule-id", default=_env("NURTUREANY_SALES_WHATSAPP_REPORT_SCHEDULE_ID", DEFAULT_SCHEDULE_ID))
    parser.add_argument("--for-date", default="", help="YYYY-MM-DD. Defaults to runtime local date.")
    parser.add_argument("--dry-run", action="store_true", help="Generate only; do not post to Slack.")
    return parser.parse_args(argv)


def _report_summary(result: dict[str, Any]) -> dict[str, Any]:
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    report = answer.get("report") if isinstance(answer.get("report"), dict) else {}
    delivery = answer.get("delivery") if isinstance(answer.get("delivery"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    return {
        "status": answer.get("status") or "unknown",
        "report_id": report.get("report_id") or "",
        "countries": ", ".join(report.get("countries") or []),
        "owner_country_rows": summary.get("owner_country_rows", 0),
        "target_account_whatsapp_count": summary.get("target_account_whatsapp_count", 0),
        "delivery_status": delivery.get("delivery_status") or "",
        "delivery_channel_id": delivery.get("delivery_channel_id") or "",
        "delivery_ts": delivery.get("delivery_ts") or "",
        "already_posted": bool(delivery.get("already_posted")),
    }


def format_result(result: dict[str, Any], schedule_id: str, dry_run: bool = False) -> str:
    if result.get("confidence") == "blocked":
        return "\n".join(
            [
                f"{AUTOMATION_PREFIX} Sales WhatsApp report blocked",
                f"Schedule: {schedule_id}",
                "Source: NurtureAny report schedule runner",
                "Confidence: blocked",
                f"Caveat: {result.get('caveat') or result.get('answer')}",
            ]
        )

    summary = _report_summary(result)
    mode = "dry run" if dry_run else summary["status"]
    lines = [
        f"{AUTOMATION_PREFIX} Sales WhatsApp report {mode}",
        f"Schedule: {schedule_id}",
        f"Report ID: {summary['report_id'] or '-'}",
        f"Countries: {summary['countries'] or '-'}",
        f"Owner-country rows: {summary['owner_country_rows']}",
        f"Target-account WhatsApp messages: {summary['target_account_whatsapp_count']}",
        f"Confidence: {result.get('confidence') or 'needs-check'}",
    ]
    if not dry_run:
        delivery_label = summary["delivery_status"] or "not-posted"
        if summary["already_posted"]:
            delivery_label = "already-posted"
        lines.extend(
            [
                f"Delivery: {delivery_label}",
                f"Channel: {summary['delivery_channel_id'] or '-'}",
                f"Slack ts: {summary['delivery_ts'] or '-'}",
            ]
        )
    if result.get("caveat"):
        lines.append(f"Caveat: {result.get('caveat')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ensure_runtime_python()
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        module = _load_hubspot_module()
        result = module.run_sales_whatsapp_window_report_schedule(args.schedule_id, for_date=args.for_date, dry_run=args.dry_run)
        print(format_result(result, args.schedule_id, args.dry_run))
        return 0 if result.get("confidence") != "blocked" else 1
    except Exception as error:
        print(
            "\n".join(
                [
                    f"{AUTOMATION_PREFIX} Sales WhatsApp report blocked",
                    f"Schedule: {args.schedule_id}",
                    "Source: NurtureAny report schedule runner",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
