#!/usr/bin/env python3
"""Deterministic Jira PCO due-date reminder digest for Hermes no-agent cron."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SAFE_FIELDS = ["summary", "status", "priority", "assignee", "updated", "duedate", "issuetype"]
FORBIDDEN_FIELD_HINTS = ["description", "comment", "transcript"]
DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_CHANNEL = "#ps-weeman-bot-test"
SILENT_PREFIX = "[SILENT] PSM Ops automation"
URL_RE = re.compile(r"https?://[^\s<>\"]+")
SLACK_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{2,}$", re.IGNORECASE)
SLACK_USERGROUP_ID_RE = re.compile(r"^S[A-Z0-9]{2,}$", re.IGNORECASE)
SLACK_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class ReminderError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _profile_dir() -> Path:
    configured = _env("HERMES_PROFILE_DIR") or _env("HERMES_HOME")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / ".hermes" / "profiles" / "psmopsbot"


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


def _timezone() -> ZoneInfo:
    timezone_name = _env("PSM_OPS_TIMEZONE", DEFAULT_TIMEZONE) or DEFAULT_TIMEZONE
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ReminderError("PSM_OPS_TIMEZONE must be a valid IANA timezone.") from error


def _parse_as_of(value: str, local_timezone: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(local_timezone)
    raw = value.strip()
    if len(raw) == 10:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as error:
            raise ReminderError("as_of must be ISO date or timestamp.") from error
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=local_timezone)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ReminderError("as_of must be ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(local_timezone)


def _default_mode(argv0: str) -> str:
    return "eod" if "eod" in Path(argv0).stem.lower() else "morning"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe PCO due-date reminder digest.")
    parser.add_argument("--mode", choices=["morning", "eod"], default=_default_mode(sys.argv[0]))
    parser.add_argument("--as-of", default="", help="ISO date/timestamp. Defaults to now in Asia/Singapore.")
    parser.add_argument("--dry-run", action="store_true", help="Mark output as a dry run. No writes are ever performed.")
    parser.add_argument("--max-results", type=int, default=50)
    return parser.parse_args(argv)


def reminder_window(mode: str, as_of: datetime) -> dict[str, Any]:
    today = as_of.date()
    if mode == "morning":
        return {
            "today": today,
            "upper_due_date": today + timedelta(days=1),
            "label": "overdue, due today, due tomorrow",
        }
    return {
        "today": today,
        "upper_due_date": today,
        "label": "overdue, due today",
    }


def _project_key() -> str:
    return _env("PSM_OPS_JIRA_PROJECT_KEY", "PCO") or "PCO"


def _ps_team_field_id() -> str:
    return _env("PSM_OPS_JIRA_FIELD_PS_TEAM") or "customfield_10876"


def _source_links_field_id() -> str:
    return _env("PSM_OPS_JIRA_FIELD_SOURCE_LINKS")


def build_jql(mode: str, as_of: datetime) -> str:
    window = reminder_window(mode, as_of)
    upper = window["upper_due_date"].isoformat()
    return (
        f"project = {_project_key()} "
        "AND statusCategory != Done "
        "AND duedate is not EMPTY "
        f'AND duedate <= "{upper}" '
        "ORDER BY duedate ASC, updated DESC"
    )


def _jira_base_url() -> str:
    value = _env("JIRA_BASE_URL", "https://staffany.atlassian.net").rstrip("/")
    if not value:
        raise ReminderError("JIRA_BASE_URL is not configured.")
    return value


def _auth_header() -> str:
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    if not email or not token:
        raise ReminderError("JIRA_EMAIL and JIRA_API_TOKEN must be configured.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def _request_json(path: str) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{_jira_base_url()}{path}",
        headers={
            "Accept": "application/json",
            "Authorization": _auth_header(),
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise ReminderError(f"Jira API returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise ReminderError(f"Jira API request failed: {error.reason}") from error


def fetch_due_issues(mode: str, as_of: datetime, max_results: int) -> list[dict[str, Any]]:
    fields = [*SAFE_FIELDS, _ps_team_field_id()]
    source_links_field = _source_links_field_id()
    if source_links_field:
        fields.append(source_links_field)
    query = urllib.parse.urlencode(
        {
            "jql": build_jql(mode, as_of),
            "fields": ",".join(fields),
            "maxResults": str(max(1, min(max_results, 100))),
        }
    )
    payload = _request_json(f"/rest/api/3/search/jql?{query}")
    issues = payload.get("issues", []) if isinstance(payload, dict) else []
    return [safe_issue(issue) for issue in issues if isinstance(issue, dict)]


def _field_value(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("value") or value.get("name") or value.get("displayName") or "Not set")
    if isinstance(value, list):
        labels = [_field_value(item) for item in value]
        labels = [label for label in labels if label and label != "Not set"]
        return ", ".join(labels) if labels else "Not set"
    return str(value or "Not set")


def _extract_links(value: Any) -> list[str]:
    links: list[str] = []

    def add_link(raw_url: str) -> None:
        url = raw_url.strip().rstrip(").,")
        if url and url not in links:
            links.append(url)

    def walk(raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, str):
            for match in URL_RE.finditer(raw):
                add_link(match.group(0))
            return
        if isinstance(raw, list):
            for item in raw:
                walk(item)
            return
        if isinstance(raw, dict):
            for nested in raw.values():
                walk(nested)

    walk(value)
    return links


def safe_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    key = str(issue.get("key") or "")
    source_links_field = _source_links_field_id()
    return {
        "key": key,
        "url": f"{_jira_base_url()}/browse/{key}" if key else _jira_base_url(),
        "summary": str(fields.get("summary") or key or "Untitled PCO issue"),
        "status": _field_value(fields.get("status")),
        "priority": _field_value(fields.get("priority")),
        "due_date": str(fields.get("duedate") or "Not set"),
        "ps_team": _field_value(fields.get(_ps_team_field_id())),
        "source_links": _extract_links(fields.get(source_links_field)) if source_links_field else [],
    }


def _bucket(due_date: str, today: date) -> str:
    try:
        parsed = date.fromisoformat(due_date)
    except ValueError:
        return "No Due Date"
    if parsed < today:
        return "Overdue"
    if parsed == today:
        return "Due Today"
    return "Due Tomorrow"


def _slack_escape(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_slack_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw.startswith(("https://", "http://")):
        return ""
    return raw.replace("|", "%7C").replace("<", "").replace(">", "")


def _format_link(url: str, label: str) -> str:
    safe_url = _safe_slack_url(url)
    if not safe_url:
        return ""
    return f"<{safe_url}|{_slack_escape(label)}>"


def _slack_channel_id_from_permalink(url: str) -> str:
    match = re.search(r"/archives/([A-Z0-9]+)/", url or "")
    return match.group(1) if match else ""


def _mention_map_path() -> str:
    return _env("PSM_OPS_REMINDER_MENTION_MAP_PATH")


def _customer_channel_map_path() -> str:
    return _env("PSM_OPS_CUSTOMER_CHANNEL_MAP_PATH")


def _load_json_file(path: str) -> Any:
    return json.loads(Path(path).expanduser().read_text(encoding="utf-8"))


def _format_mention_target(target: dict[str, Any]) -> str:
    target_type = str(target.get("type") or "").strip().lower()
    target_id = str(target.get("id") or "").strip().upper()
    if target_type == "user" and SLACK_USER_ID_RE.fullmatch(target_id):
        return f"<@{target_id}>"
    if target_type == "usergroup" and SLACK_USERGROUP_ID_RE.fullmatch(target_id):
        handle = str(target.get("handle") or target.get("label") or "team").strip().lstrip("@")
        handle = handle if SLACK_HANDLE_RE.fullmatch(handle) else "team"
        return f"<!subteam^{target_id}|{handle}>"
    return ""


def load_mention_map() -> tuple[dict[str, list[str]], str]:
    path = _mention_map_path()
    if not path:
        return {}, ""
    try:
        payload = _load_json_file(path)
    except (OSError, json.JSONDecodeError):
        return {}, "PSM_OPS_REMINDER_MENTION_MAP_PATH could not be read; mentions disabled."
    ps_teams = payload.get("ps_teams") if isinstance(payload, dict) else None
    if not isinstance(ps_teams, dict):
        return {}, "PSM_OPS_REMINDER_MENTION_MAP_PATH has invalid shape; mentions disabled."

    mentions: dict[str, list[str]] = {}
    for team, targets in ps_teams.items():
        team_name = str(team or "").strip()
        if not team_name:
            continue
        target_list = targets if isinstance(targets, list) else [targets]
        rendered = [
            mention
            for target in target_list
            if isinstance(target, dict)
            for mention in [_format_mention_target(target)]
            if mention
        ]
        if rendered:
            mentions[team_name] = rendered
    return mentions, ""


def load_customer_channel_map() -> dict[str, dict[str, str]]:
    path = _customer_channel_map_path()
    if not path:
        return {}
    try:
        payload = _load_json_file(path)
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(payload, list):
        entries = payload
    elif isinstance(payload, dict):
        entries = payload.get("channels") or payload.get("mappings") or []
    else:
        return {}
    if not isinstance(entries, list):
        return {}

    channels: dict[str, dict[str, str]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        channel_id = str(entry.get("channel_id") or "").strip()
        channel_name = str(entry.get("channel_name") or "").strip()
        status = str(entry.get("status") or "").strip().lower()
        if channel_id and channel_name and status == "reviewed":
            channels[channel_id] = {"channel_id": channel_id, "channel_name": channel_name}
    return channels


def load_reminder_context() -> dict[str, Any]:
    mentions, mention_warning = load_mention_map()
    return {
        "mentions": mentions,
        "mention_warning": mention_warning,
        "customer_channels": load_customer_channel_map(),
    }


def _format_source_links(issue: dict[str, Any]) -> str:
    rendered: list[str] = []
    for index, link in enumerate(issue.get("source_links") or [], start=1):
        label = "source thread" if _slack_channel_id_from_permalink(str(link)) else f"source {index}"
        formatted = _format_link(str(link), label)
        if formatted:
            rendered.append(formatted)
    return ", ".join(rendered[:5])


def _customer_channel_for_issue(issue: dict[str, Any], customer_channels: dict[str, dict[str, str]]) -> str:
    for link in issue.get("source_links") or []:
        channel_id = _slack_channel_id_from_permalink(str(link))
        if not channel_id or channel_id not in customer_channels:
            continue
        channel = customer_channels[channel_id]
        channel_name = _slack_escape(channel.get("channel_name") or channel_id)
        return f"<#{channel_id}|{channel_name}>"
    return ""


def _format_issue(issue: dict[str, Any], customer_channels: dict[str, dict[str, str]]) -> list[str]:
    source_links = _format_source_links(issue)
    customer_channel = _customer_channel_for_issue(issue, customer_channels)
    lines = [
        f"- {_format_link(issue['url'], issue['key'])} - {_slack_escape(issue['summary'])}",
        (
            f"  Status: {_slack_escape(issue['status'])} | Priority: {_slack_escape(issue['priority'])} | "
            f"Due: {_slack_escape(issue['due_date'])} | PS Team: {_slack_escape(issue['ps_team'])}"
        ),
    ]
    if source_links:
        lines.append(f"  Source: {source_links}")
    if customer_channel:
        lines.append(f"  Customer team: {customer_channel}")
    return [
        line for line in lines if line
    ]


def format_digest(
    issues: list[dict[str, Any]],
    mode: str,
    as_of: datetime,
    dry_run: bool = False,
    context: dict[str, Any] | None = None,
) -> str:
    window = reminder_window(mode, as_of)
    today = window["today"]
    if not issues:
        dry = " Dry run." if dry_run else ""
        return (
            f"{SILENT_PREFIX}: no PCO due-date reminders for {today.isoformat()} "
            f"({mode}; {window['label']}).{dry}"
        )

    reminder_context = context or load_reminder_context()
    mentions = reminder_context.get("mentions") if isinstance(reminder_context.get("mentions"), dict) else {}
    mention_warning = str(reminder_context.get("mention_warning") or "").strip()
    customer_channels = (
        reminder_context.get("customer_channels")
        if isinstance(reminder_context.get("customer_channels"), dict)
        else {}
    )

    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for issue in issues:
        grouped[issue.get("ps_team") or "Not set"][_bucket(issue.get("due_date", ""), today)].append(issue)

    mention_gaps = [
        ps_team
        for ps_team in sorted(grouped)
        if ps_team != "Not set" and not mentions.get(ps_team)
    ]
    dry_label = " DRY RUN" if dry_run else ""
    lines = [
        f"PSM Ops automation: PCO due-date reminder{dry_label} - {today.isoformat()}",
        f"*Mode:* {_slack_escape(mode)} | *Window:* {_slack_escape(window['label'])}",
        "*Source:* Jira PCO `duedate`; central digest only",
        f"*Total issues:* {len(issues)}",
    ]
    bucket_order = ["Overdue", "Due Today", "Due Tomorrow", "No Due Date"]
    for ps_team in sorted(grouped):
        lines.append("")
        mention_text = " ".join(mentions.get(ps_team) or [])
        suffix = f" {mention_text}" if mention_text else ""
        lines.append(f"*PS Team: {_slack_escape(ps_team)}*{suffix}")
        for bucket_name in bucket_order:
            bucket_issues = grouped[ps_team].get(bucket_name) or []
            if not bucket_issues:
                continue
            lines.append(f"*{_slack_escape(bucket_name)}*")
            for issue in bucket_issues:
                lines.extend(_format_issue(issue, customer_channels))
    if mention_gaps:
        lines.append("")
        lines.append(f"Mention gaps: {_slack_escape(', '.join(mention_gaps))}")
    if mention_warning:
        lines.append(f"Mention map warning: {_slack_escape(mention_warning)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        local_timezone = _timezone()
        as_of = _parse_as_of(args.as_of, local_timezone)
        issues = fetch_due_issues(args.mode, as_of, args.max_results)
        print(format_digest(issues, args.mode, as_of, args.dry_run))
        return 0
    except ReminderError as error:
        print(
            "\n".join(
                [
                    "PSM Ops automation: due-date reminder blocked",
                    "Source: Jira PCO",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
