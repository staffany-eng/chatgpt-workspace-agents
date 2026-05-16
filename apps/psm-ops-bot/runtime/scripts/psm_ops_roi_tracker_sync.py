#!/usr/bin/env python3
"""Deterministic ROI-to-PCO tracker sync for Hermes no-agent cron."""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Singapore"
ROI_TRACKER_LABEL = "ps-wee-roi-tracker"
SILENT_PREFIX = "[SILENT] PSM Ops automation"


class RoiTrackerSyncError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _profile_dir() -> Path:
    configured = _env("HERMES_PROFILE_DIR") or _env("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".hermes" / "profiles" / "psmopsbot"


def load_profile_env() -> None:
    env_path = _profile_dir() / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _timezone() -> ZoneInfo:
    timezone_name = _env("PSM_OPS_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise RoiTrackerSyncError("PSM_OPS_TIMEZONE must be a valid IANA timezone.") from error


def _parse_as_of(value: str, local_timezone: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(local_timezone)
    raw = value.strip()
    if len(raw) == 10:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as error:
            raise RoiTrackerSyncError("as_of must be ISO date or timestamp.") from error
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=local_timezone)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise RoiTrackerSyncError("as_of must be ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(local_timezone)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wake PCO customer-loop trackers when linked ROI tickets are done.")
    parser.add_argument("--as-of", default="", help="ISO date/timestamp. Defaults to now in Asia/Singapore.")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without mutating Jira.")
    parser.add_argument("--max-results", type=int, default=50)
    return parser.parse_args(argv)


def _project_key() -> str:
    return _env("PSM_OPS_JIRA_PROJECT_KEY", "PCO") or "PCO"


def _roi_project_key() -> str:
    value = _env("PSM_OPS_ROI_JIRA_PROJECT_KEY", "ROI") or "ROI"
    if "," in value:
        raise RoiTrackerSyncError("PSM_OPS_ROI_JIRA_PROJECT_KEY must contain exactly one project key.")
    return value.upper()


def _jira_base_url() -> str:
    value = _env("JIRA_BASE_URL", "https://staffany.atlassian.net").rstrip("/")
    if not value:
        raise RoiTrackerSyncError("JIRA_BASE_URL is not configured.")
    return value


def _auth_header() -> str:
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    if not email or not token:
        raise RoiTrackerSyncError("JIRA_EMAIL and JIRA_API_TOKEN must be configured.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _request_json(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{_jira_base_url()}{path}",
        data=data,
        headers={
            "Accept": "application/json",
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload) if payload else {}
    except Exception as error:  # noqa: BLE001 - keep no-agent failure concise.
        raise RoiTrackerSyncError(f"Jira API request failed: {error}") from error


def _quote_jql(value: str) -> str:
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def build_jql() -> str:
    return (
        f"project = {_project_key()} "
        f"AND labels = {_quote_jql(ROI_TRACKER_LABEL)} "
        'AND status = "Waiting Internal" '
        "ORDER BY updated ASC"
    )


def _issue_url(issue_key: str) -> str:
    key = (issue_key or "").strip().upper()
    return f"{_jira_base_url()}/browse/{key}" if key else _jira_base_url()


def _field_text(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or value.get("value") or value.get("displayName") or "Not set")
    return str(value or "Not set")


def _linked_roi_key(issue: dict[str, Any]) -> str:
    fields = issue.get("fields") or {}
    links = fields.get("issuelinks") or []
    prefix = f"{_roi_project_key()}-"
    for link in links if isinstance(links, list) else []:
        for side in ("inwardIssue", "outwardIssue"):
            key = str(((link.get(side) or {}).get("key")) or "").strip().upper()
            if key.startswith(prefix):
                return key
    return ""


def safe_tracker(issue: dict[str, Any]) -> dict[str, str]:
    fields = issue.get("fields") or {}
    key = str(issue.get("key") or "").strip().upper()
    return {
        "key": key,
        "url": _issue_url(key),
        "summary": str(fields.get("summary") or key or "Untitled PCO ROI tracker"),
        "status": _field_text(fields.get("status")),
        "roi_issue_key": _linked_roi_key(issue),
    }


def fetch_trackers(max_results: int) -> list[dict[str, str]]:
    query = urllib.parse.urlencode(
        {
            "jql": build_jql(),
            "fields": "summary,status,issuelinks,labels,updated",
            "maxResults": str(max(1, min(max_results, 100))),
        }
    )
    payload = _request_json("GET", f"/rest/api/3/search/jql?{query}")
    issues = payload.get("issues", []) if isinstance(payload, dict) else []
    return [safe_tracker(issue) for issue in issues if isinstance(issue, dict)]


def fetch_roi_issue(roi_issue_key: str) -> dict[str, str]:
    key = (roi_issue_key or "").strip().upper()
    payload = _request_json("GET", f"/rest/api/3/issue/{urllib.parse.quote(key)}?fields=summary,status")
    fields = payload.get("fields") or {}
    status = fields.get("status") or {}
    category = status.get("statusCategory") if isinstance(status, dict) else {}
    return {
        "key": key,
        "url": _issue_url(key),
        "summary": str(fields.get("summary") or key),
        "status": _field_text(status),
        "status_category": str((category or {}).get("key") or (category or {}).get("name") or "").lower(),
    }


def _roi_is_done(roi_issue: dict[str, str]) -> bool:
    return roi_issue.get("status_category") == "done" or roi_issue.get("status", "").strip().lower() == "done"


def _adf(text: str) -> dict[str, Any]:
    return {
        "type": "doc",
        "version": 1,
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def add_internal_comment(issue_key: str, comment: str) -> None:
    _request_json(
        "POST",
        f"/rest/servicedeskapi/request/{urllib.parse.quote(issue_key)}/comment",
        {"body": comment.strip(), "public": False},
    )


def transition_issue(issue_key: str, target_status: str) -> None:
    payload = _request_json("GET", f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/transitions")
    target = target_status.strip().lower()
    selected = next(
        (
            transition
            for transition in payload.get("transitions", [])
            if str(transition.get("name") or "").strip().lower() == target
            or str((transition.get("to") or {}).get("name") or "").strip().lower() == target
        ),
        None,
    )
    if not selected:
        raise RoiTrackerSyncError(f"No Jira transition to {target_status} is available for {issue_key}.")
    _request_json("POST", f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/transitions", {"transition": {"id": selected["id"]}})


def set_due_date(issue_key: str, due_date: date) -> None:
    _request_json("PUT", f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}", {"fields": {"duedate": due_date.isoformat()}})


def wake_tracker(tracker: dict[str, str], roi_issue: dict[str, str], today: date) -> None:
    comment = (
        "ROI tracker sync: linked ROI ticket is Done.\n"
        f"ROI issue: {roi_issue['key']} {roi_issue['url']}\n"
        "Next step: PS to close the loop with the customer."
    )
    add_internal_comment(tracker["key"], comment)
    transition_issue(tracker["key"], "Open")
    set_due_date(tracker["key"], today)


def sync_trackers(trackers: list[dict[str, str]], as_of: datetime, dry_run: bool = False) -> dict[str, Any]:
    today = as_of.date()
    changed: list[dict[str, str]] = []
    blocked: list[dict[str, str]] = []
    for tracker in trackers:
        roi_key = tracker.get("roi_issue_key", "")
        if not roi_key:
            blocked.append({**tracker, "reason": "missing linked ROI issue"})
            continue
        try:
            roi_issue = fetch_roi_issue(roi_key)
            if not _roi_is_done(roi_issue):
                continue
            if not dry_run:
                wake_tracker(tracker, roi_issue, today)
            changed.append({**tracker, "roi_status": roi_issue["status"], "roi_url": roi_issue["url"]})
        except RoiTrackerSyncError as error:
            blocked.append({**tracker, "reason": str(error)})
    return {"checked": len(trackers), "changed": changed, "blocked": blocked, "date": today.isoformat(), "dry_run": dry_run}


def format_result(result: dict[str, Any]) -> str:
    changed = result.get("changed") or []
    blocked = result.get("blocked") or []
    if not changed and not blocked:
        return f"{SILENT_PREFIX}: no ROI tracker changes for {result['date']} (checked {result['checked']})."
    dry = " DRY RUN" if result.get("dry_run") else ""
    lines = [
        f"PSM Ops automation: ROI tracker sync{dry} - {result['date']}",
        "Source: Jira ROI linked to Jira PCO",
        f"Checked trackers: {result['checked']}",
        f"Changed trackers: {len(changed)}",
        f"Blocked trackers: {len(blocked)}",
    ]
    if changed:
        lines.append("")
        lines.append("Ready for customer loop:")
        for item in changed:
            lines.append(f"- <{item['url']}|{item['key']}> - linked ROI done: <{item.get('roi_url')}|{item.get('roi_issue_key')}>")
    if blocked:
        lines.append("")
        lines.append("Needs attention:")
        for item in blocked:
            lines.append(f"- <{item['url']}|{item['key']}> - {item.get('reason')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        local_timezone = _timezone()
        as_of = _parse_as_of(args.as_of, local_timezone)
        trackers = fetch_trackers(args.max_results)
        print(format_result(sync_trackers(trackers, as_of, args.dry_run)))
        return 0
    except RoiTrackerSyncError as error:
        print(
            "\n".join(
                [
                    "PSM Ops automation: ROI tracker sync blocked",
                    "Source: Jira ROI linked to Jira PCO",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
