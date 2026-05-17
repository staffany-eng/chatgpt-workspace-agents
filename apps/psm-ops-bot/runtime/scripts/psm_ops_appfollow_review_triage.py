#!/usr/bin/env python3
"""Event-driven AppFollow review triage from a Slack alert permalink.

This is intentionally not a polling job. It hydrates one #all-reviews alert,
posts one bot-owned triage reply when --apply is passed, and records runtime
state keyed by store + ext_id + review_id.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
PROFILE_RUNTIME_MCP_DIR = SCRIPT_PATH.parents[1] / "runtime" / "mcp"
SOURCE_RUNTIME_MCP_DIR = SCRIPT_PATH.parents[1] / "mcp"
MCP_DIR = PROFILE_RUNTIME_MCP_DIR if PROFILE_RUNTIME_MCP_DIR.exists() else SOURCE_RUNTIME_MCP_DIR
if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))

from appfollow_reviews_core import (  # noqa: E402
    IDENTITY_TAG_REQUESTED_PRIVATE,
    STAFFANY_SUPPORT_EMAIL,
    already_triaged,
    classify_appfollow_review,
    draft_appfollow_reply,
    extract_appfollow_review_from_slack_message,
    get_appfollow_review,
    mark_triaged,
    state_summary,
)
from profile_env import load_profile_env  # noqa: E402
from psm_slack_notifier import _slack_get, _slack_post, parse_slack_permalink, redact_text  # noqa: E402


def _json_line(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, default=str)


def _fetch_alert_message(slack_thread_url: str) -> dict[str, Any]:
    parsed = parse_slack_permalink(slack_thread_url)
    if not parsed.get("channel_id") or not parsed.get("thread_ts"):
        raise RuntimeError("Unable to parse Slack thread permalink.")
    payload = _slack_get(
        "conversations.replies",
        {
            "channel": parsed["channel_id"],
            "ts": parsed["thread_ts"],
            "limit": "20",
            "inclusive": "true",
        },
    )
    messages = payload.get("messages") if isinstance(payload, dict) else []
    target_ts = parsed.get("message_ts") or parsed.get("thread_ts")
    for message in messages if isinstance(messages, list) else []:
        if isinstance(message, dict) and str(message.get("ts") or "") == target_ts:
            return message
    for message in messages if isinstance(messages, list) else []:
        if isinstance(message, dict):
            return message
    raise RuntimeError("Slack thread returned no messages.")


def _canonical_review(extracted: dict[str, Any]) -> dict[str, Any]:
    if not extracted.get("ext_id") and not extracted.get("collection_name"):
        return {
            "status": "skipped",
            "reason": (
                "No AppFollow ext_id or collection_name was resolved from Slack alert. Configure "
                "PSM_OPS_APPFOLLOW_APP_EXT_IDS, PSM_OPS_APPFOLLOW_DEFAULT_EXT_ID, "
                "PSM_OPS_APPFOLLOW_COLLECTION_NAMES, or PSM_OPS_APPFOLLOW_DEFAULT_COLLECTION_NAME."
            ),
        }
    result = get_appfollow_review(
        ext_id=extracted.get("ext_id", ""),
        collection_name=extracted.get("collection_name", ""),
        review_id=extracted.get("review_id", ""),
    )
    if result.get("confidence") == "blocked":
        return {"status": "blocked", "reason": result.get("caveat") or result.get("answer")}
    return {"status": "verified", "payload": result.get("answer")}


def _one_line(value: str, limit: int = 180) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "..."


def _build_slack_text(
    extracted: dict[str, Any],
    canonical: dict[str, Any],
    slack_thread_url: str,
    duplicate: bool,
) -> str:
    classification = classify_appfollow_review(extracted)
    draft = draft_appfollow_reply(extracted)
    answer_text = ((draft.get("answer") or {}) if isinstance(draft, dict) else {}).get("answer_text", "")
    rating = extracted.get("rating")
    stars = f"{rating}/5" if rating else "unknown rating"
    title = extracted.get("title") or "Untitled review"
    app_version = extracted.get("app_version") or "unknown app version"
    country = extracted.get("country") or "unknown country"
    hydrate_status = canonical.get("status", "unknown")
    action_line = (
        f"Actions: `tag {IDENTITY_TAG_REQUESTED_PRIVATE}`, `draft reply`, then watch for private follow-up at "
        f"{STAFFANY_SUPPORT_EMAIL}. `post reply` only after the approved reply is final."
    )
    if duplicate:
        action_line = "Duplicate guard: already triaged; no new action posted unless --force was used."
    lines = [
        "PSM Ops automation: AppFollow review triage",
        f"Review: {stars} {extracted.get('store') or 'unknown store'} {country} {app_version} - {_one_line(title, 120)}",
        f"Review ID: {extracted.get('review_id') or 'missing'}",
        f"Theme: {classification['theme']} | Severity: {classification['severity']}",
        f"Canonical AppFollow fetch: {hydrate_status}",
    ]
    if canonical.get("reason"):
        lines.append(f"Fetch note: {_one_line(str(canonical['reason']), 160)}")
    if extracted.get("appfollow_url"):
        lines.append(f"AppFollow: {extracted['appfollow_url']}")
    lines.extend(
        [
            f"Source Slack alert: {slack_thread_url}",
            action_line,
            (
                "Identity: unknown until the reviewer follows up privately with their StaffAny account email or phone "
                "plus company/outlet. Do not ask for email/phone in the public review."
            ),
            f"Internal correlation: keep this Slack thread tied to review_id {extracted.get('review_id') or 'missing'}.",
            f"Draft reply for approval: {_one_line(answer_text, 300)}",
            "Caveat: reviewer nickname is not enough to map a StaffAny customer/org. Use private support follow-up plus Customer 360/Jira evidence for internal follow-up.",
        ]
    )
    return redact_text("\n".join(lines))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Hydrate and triage one AppFollow review Slack alert.")
    parser.add_argument("--slack-thread-url", required=True, help="Slack permalink for the AppFollow #all-reviews alert.")
    parser.add_argument("--apply", action="store_true", help="Post the bot-owned triage reply and persist idempotency state.")
    parser.add_argument("--force", action="store_true", help="Post even if the review key is already triaged.")
    parser.add_argument("--state-path", default="", help="Override PSM_OPS_APPFOLLOW_STATE_PATH for tests or one-off runs.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    load_profile_env()
    args = parse_args(argv)
    alert_message = _fetch_alert_message(args.slack_thread_url)
    extracted = extract_appfollow_review_from_slack_message(alert_message)
    if not extracted.get("review_id"):
        print("appfollow_review_triage:blocked:review_id_missing")
        print(_json_line({"extracted": extracted}))
        return 1
    duplicate = already_triaged(extracted, state_path=args.state_path)
    if duplicate and not args.force:
        print(f"appfollow_review_triage:skipped:duplicate:{state_summary(extracted, state_path=args.state_path)['key']}")
        return 0

    canonical = _canonical_review(extracted)
    text = _build_slack_text(extracted, canonical, args.slack_thread_url, duplicate)
    if not args.apply:
        print("appfollow_review_triage:dry_run")
        print(text)
        print(_json_line({"state": mark_triaged(extracted, slack_thread_url=args.slack_thread_url, state_path=args.state_path, dry_run=True)}))
        return 0

    parsed = parse_slack_permalink(args.slack_thread_url)
    payload = _slack_post(
        "chat.postMessage",
        {
            "channel": parsed["channel_id"],
            "thread_ts": parsed["thread_ts"],
            "text": text,
            "unfurl_links": False,
            "unfurl_media": False,
        },
    )
    state = mark_triaged(extracted, slack_thread_url=args.slack_thread_url, state_path=args.state_path)
    print(_json_line({"posted": {"channel": payload.get("channel"), "ts": payload.get("ts")}, "state": state}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
