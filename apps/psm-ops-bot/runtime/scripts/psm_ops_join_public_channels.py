#!/usr/bin/env python3
"""Join the PSM Ops Slack bot to public/open channels using bot-owned auth."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


DEFAULT_PROFILE = "psmopsbot"
DEFAULT_PAGE_LIMIT = 200

SlackApi = Callable[[str, dict[str, str], bool], dict[str, Any]]


def _profile_dir() -> Path:
    configured = os.environ.get("HERMES_PROFILE_DIR") or os.environ.get("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".hermes" / "profiles" / DEFAULT_PROFILE


def load_profile_env() -> None:
    """Load profile .env values without overriding explicit process env."""
    env_path = _profile_dir() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip('"').strip("'")


def slack_api(method: str, params: dict[str, str], post: bool = False) -> dict[str, Any]:
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        return {"ok": False, "error": "missing_slack_bot_token"}
    data = urllib.parse.urlencode(params).encode("utf-8") if post else None
    url = f"https://slack.com/api/{method}"
    if params and not post:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST" if post else "GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - safe CLI should report, not leak stack.
        return {"ok": False, "error": f"{exc.__class__.__name__}"}


def list_public_channels(api: SlackApi = slack_api, page_limit: int = DEFAULT_PAGE_LIMIT) -> tuple[list[dict[str, Any]], str]:
    channels: list[dict[str, Any]] = []
    cursor = ""
    while True:
        params = {
            "types": "public_channel",
            "exclude_archived": "true",
            "limit": str(page_limit),
        }
        if cursor:
            params["cursor"] = cursor
        payload = api("conversations.list", params, False)
        if not payload.get("ok"):
            return channels, str(payload.get("error") or "unknown_error")
        for channel in payload.get("channels") or []:
            if isinstance(channel, dict):
                channels.append(channel)
        cursor = str(((payload.get("response_metadata") or {}).get("next_cursor") or "")).strip()
        if not cursor:
            return channels, ""


def _safe_channel(channel: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(channel.get("id") or ""),
        "name": str(channel.get("name") or ""),
        "is_member": bool(channel.get("is_member")),
        "is_archived": bool(channel.get("is_archived")),
    }


def plan_public_channel_joins(
    channels: list[dict[str, Any]],
    *,
    only_channel_ids: set[str] | None = None,
    max_channels: int | None = None,
) -> dict[str, Any]:
    safe_channels = [_safe_channel(channel) for channel in channels]
    if only_channel_ids:
        safe_channels = [channel for channel in safe_channels if channel["id"] in only_channel_ids]
    safe_channels = [channel for channel in safe_channels if channel["id"] and not channel["is_archived"]]
    already_member = [channel for channel in safe_channels if channel["is_member"]]
    candidates = [channel for channel in safe_channels if not channel["is_member"]]
    if max_channels is not None:
        candidates = candidates[: max(0, max_channels)]
    return {
        "visible_public_channels": len(safe_channels),
        "already_member": len(already_member),
        "join_candidates": candidates,
        "would_join": len(candidates),
    }


def join_public_channels(
    channels: list[dict[str, Any]],
    *,
    apply: bool,
    only_channel_ids: set[str] | None = None,
    max_channels: int | None = None,
    api: SlackApi = slack_api,
) -> dict[str, Any]:
    plan = plan_public_channel_joins(channels, only_channel_ids=only_channel_ids, max_channels=max_channels)
    result: dict[str, Any] = {
        "mode": "apply" if apply else "dry-run",
        "visible_public_channels": plan["visible_public_channels"],
        "already_member": plan["already_member"],
        "would_join": plan["would_join"],
        "joined": 0,
        "failed": [],
    }
    if not apply:
        return result
    for channel in plan["join_candidates"]:
        payload = api("conversations.join", {"channel": channel["id"]}, True)
        if payload.get("ok"):
            result["joined"] += 1
            continue
        result["failed"].append(
            {
                "channel_id": channel["id"],
                "channel_name": channel["name"],
                "error": str(payload.get("error") or "unknown_error"),
            }
        )
    return result


def _print_result(result: dict[str, Any], *, json_output: bool) -> None:
    if json_output:
        print(json.dumps(result, indent=2, sort_keys=True))
        return
    print(
        "slack:public-channel-join:"
        f"mode={result.get('mode')}:"
        f"visible={result.get('visible_public_channels')}:"
        f"already_member={result.get('already_member')}:"
        f"would_join={result.get('would_join')}:"
        f"joined={result.get('joined')}:"
        f"failed={len(result.get('failed') or [])}"
    )
    for failure in result.get("failed") or []:
        print(
            "slack:public-channel-join-failed:"
            f"channel={failure.get('channel_id')}:"
            f"name={failure.get('channel_name')}:"
            f"error={failure.get('error')}"
        )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Join PS WEE to public/open Slack channels.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Mutate Slack by joining missing public channels.")
    mode.add_argument("--dry-run", action="store_true", help="Only report what would be joined. This is the default.")
    parser.add_argument("--channel-id", action="append", default=[], help="Limit to one public channel ID. Repeatable.")
    parser.add_argument("--max-channels", type=int, default=None, help="Cap join candidates for staged rollout.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of compact status lines.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    load_profile_env()
    channels, error = list_public_channels()
    if error:
        result = {"ok": False, "error": error, "mode": "apply" if args.apply else "dry-run"}
        _print_result(result, json_output=args.json)
        return 1
    result = join_public_channels(
        channels,
        apply=bool(args.apply),
        only_channel_ids=set(args.channel_id) if args.channel_id else None,
        max_channels=args.max_channels,
    )
    _print_result(result, json_output=args.json)
    failures = result.get("failed") or []
    if any(failure.get("error") == "missing_scope" for failure in failures):
        return 2
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
