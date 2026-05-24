#!/usr/bin/env python3
"""Local read-only probe for scoped HubSpot WhatsApp window data."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


RUNTIME_ROOT = Path(__file__).resolve().parents[1]
APP_ROOT = RUNTIME_ROOT.parent
WORKSPACE_ROOT = APP_ROOT.parents[1]
MCP_DIR = RUNTIME_ROOT / "mcp"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def load_local_env() -> None:
    for path in (
        WORKSPACE_ROOT / ".env",
        APP_ROOT / ".env",
        Path.home() / ".hermes" / ".env",
    ):
        _load_dotenv(path)


def default_yesterday_sgt() -> str:
    return (datetime.now(ZoneInfo("Asia/Singapore")).date() - timedelta(days=1)).isoformat()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect safe HubSpot WhatsApp metadata for one owner/window.")
    parser.add_argument("--caller-email", default="eugene@staffany.com")
    parser.add_argument("--owner-email", required=True)
    parser.add_argument("--for-date", default=default_yesterday_sgt(), help="YYYY-MM-DD; defaults to yesterday in SGT.")
    parser.add_argument("--countries", default="Singapore,Malaysia", help="Comma-separated countries.")
    parser.add_argument("--start", default="09:30")
    parser.add_argument("--end", default="10:30")
    parser.add_argument("--timezone", default="Asia/Singapore")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    return parser.parse_args(argv)


def _first_local_time(messages: list[dict[str, Any]]) -> str:
    if not messages:
        return ""
    local = str(messages[0].get("timestamp_local") or "")
    try:
        return datetime.fromisoformat(local).strftime("%-I:%M%p").lower()
    except ValueError:
        return local


def compact_result(result: dict[str, Any], sample_count: int) -> dict[str, Any]:
    answer = result.get("answer") if isinstance(result.get("answer"), dict) else {}
    messages = answer.get("all_target_account_messages") if isinstance(answer.get("all_target_account_messages"), list) else []
    return {
        "confidence": result.get("confidence"),
        "caveat": result.get("caveat"),
        "source": result.get("source"),
        "scope": result.get("scope"),
        "owner_email": answer.get("owner_email"),
        "date": answer.get("date"),
        "timezone": answer.get("timezone"),
        "local_window": answer.get("local_window"),
        "utc_window": answer.get("utc_window"),
        "owner_whatsapp_sent_count": answer.get("owner_whatsapp_sent_count"),
        "target_account_whatsapp_sent_count": answer.get("target_account_whatsapp_sent_count"),
        "target_account_count_scanned": answer.get("target_account_count_scanned"),
        "target_account_count_with_whatsapp": answer.get("target_account_count_with_whatsapp"),
        "first_target_account_sent": _first_local_time(messages),
        "messages_missing_kns_count": answer.get("messages_missing_kns_count"),
        "body_unavailable_count": answer.get("body_unavailable_count"),
        "truncated": result.get("truncated"),
        "returned_count": result.get("returned_count"),
        "sample_target_messages": messages[: max(0, sample_count)],
        "raw_bodies_returned": answer.get("raw_bodies_returned", False),
        "will_mutate_hubspot": answer.get("will_mutate_hubspot", False),
    }


def print_human(data: dict[str, Any]) -> None:
    print(f"Owner: {data.get('owner_email')}")
    print(f"Date: {data.get('date')}")
    print(f"Window: {data.get('local_window')}")
    print(f"Owner WhatsApp sent: {data.get('owner_whatsapp_sent_count')}")
    print(f"Target-account WhatsApp sent: {data.get('target_account_whatsapp_sent_count')}")
    print(f"Target accounts scanned: {data.get('target_account_count_scanned')}")
    print(f"Target accounts with WhatsApp: {data.get('target_account_count_with_whatsapp')}")
    print(f"First target-account sent: {data.get('first_target_account_sent') or '-'}")
    print(f"Truncated: {data.get('truncated')}")
    print(f"Confidence: {data.get('confidence')}")
    print("")
    print("Sample target-account messages:")
    for message in data.get("sample_target_messages") or []:
        accounts = ", ".join(account.get("company_name") or account.get("company_id") or "" for account in message.get("target_accounts", []))
        print(
            "- "
            f"{message.get('timestamp_local') or message.get('timestamp')} | "
            f"{accounts or '-'} | "
            f"communication_id={message.get('object_id')}"
        )
    if data.get("caveat"):
        print("")
        print(f"Caveat: {data.get('caveat')}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_local_env()
    if str(MCP_DIR) not in sys.path:
        sys.path.insert(0, str(MCP_DIR))

    import hubspot_nurtureany_server as hubspot

    countries = [country.strip() for country in args.countries.split(",") if country.strip()]
    result = hubspot.audit_owner_whatsapp_kns_window(
        slack_user_email=args.caller_email,
        owner_email=args.owner_email,
        countries=countries,
        for_date=args.for_date,
        whatsapp_window_start_local=args.start,
        whatsapp_window_end_local=args.end,
        timezone_override_by_owner_email={args.owner_email: args.timezone},
        limit=args.limit,
    )
    data = compact_result(result, args.samples)
    if args.json:
        print(json.dumps(data, indent=2, default=str))
    else:
        print_human(data)
    return 0 if result.get("confidence") != "blocked" else 1


if __name__ == "__main__":
    raise SystemExit(main())
