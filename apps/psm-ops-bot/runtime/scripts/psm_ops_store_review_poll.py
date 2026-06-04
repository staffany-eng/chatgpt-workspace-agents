#!/usr/bin/env python3
"""No-agent direct store review poller for PSM Ops Bot.

Hermes cron delivers stdout to Slack. This script prints one bot-owned
`PSM Ops automation: Store review triage` block only when a new or changed review is found.
Cron/no-arg runs persist state; dry runs never persist state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
PROFILE_RUNTIME_MCP_DIR = SCRIPT_PATH.parents[1] / "runtime" / "mcp"
SOURCE_RUNTIME_MCP_DIR = SCRIPT_PATH.parents[1] / "mcp"
MCP_DIR = PROFILE_RUNTIME_MCP_DIR if PROFILE_RUNTIME_MCP_DIR.exists() else SOURCE_RUNTIME_MCP_DIR
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from profile_env import load_profile_env  # noqa: E402
from store_reviews_core import (  # noqa: E402
    build_slack_triage_text,
    mark_triaged,
    poll_new_reviews,
    state_summary,
)


def _json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Poll direct App Store / Google Play reviews.")
    parser.add_argument("--store", default="", choices=["", "app_store", "google_play"], help="Store to poll; default polls both.")
    parser.add_argument("--limit", type=int, default=20, help="Max reviews per store to inspect.")
    parser.add_argument("--lookback-days", type=int, default=7, help="Review updated/created lookback window.")
    parser.add_argument("--state-path", default="", help="Override PSM_OPS_STORE_REVIEWS_STATE_PATH for tests.")
    parser.add_argument("--apply", action="store_true", help="Persist triage state. This is the default and is kept for explicit operator runs.")
    parser.add_argument("--dry-run", action="store_true", help="Preview Slack output without persisting triage state.")
    parser.add_argument("--include-changed", action="store_true", default=True, help="Also triage reviews whose content changed.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    load_profile_env()
    args = parse_args(argv)
    result = poll_new_reviews(
        store=args.store,
        limit=args.limit,
        lookback_days=args.lookback_days,
        state_path=args.state_path,
        include_changed=args.include_changed,
    )
    if result.get("confidence") == "blocked":
        print(f"PSM Ops automation: Store review poll blocked\nCaveat: {result.get('caveat')}")
        print(_json_line({"status": "blocked", "scope": result.get("scope", {})}))
        return 1

    answer = result.get("answer") or {}
    reviews = answer.get("reviews") or []
    store_errors = answer.get("store_errors") or []
    if not reviews:
        if store_errors:
            print("PSM Ops automation: Store review poll partial")
            print("Caveat: one or more store review sources failed; no new reviews were returned by available stores.")
            print(_json_line({"status": "partial", "store_errors": store_errors, "skipped_duplicate_keys": answer.get("skipped_duplicate_keys", [])}))
            return 1
        print("[SILENT] PSM Ops automation: store review poll no new reviews")
        print(_json_line({"status": "no_new_reviews", "skipped_duplicate_keys": answer.get("skipped_duplicate_keys", [])}))
        return 0

    messages: list[str] = []
    stored: list[dict[str, Any]] = []
    dry_run = bool(args.dry_run)
    for review in reviews:
        summary = state_summary(review, state_path=args.state_path)
        messages.append(build_slack_triage_text(review, changed=bool(summary.get("changed"))))
        stored.append(mark_triaged(review, state_path=args.state_path, dry_run=dry_run))

    if dry_run:
        print("store_review_poll:dry_run")
    if store_errors:
        print("PSM Ops automation: Store review poll partial")
        print("Caveat: one or more store review sources failed; available triage below is from stores that responded.")
    print("\n\n".join(messages))
    print(_json_line({"status": "preview" if dry_run else "stored", "state": stored, "store_errors": store_errors}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
