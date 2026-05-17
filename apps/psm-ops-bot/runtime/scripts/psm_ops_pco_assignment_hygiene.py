#!/usr/bin/env python3
"""Deterministic Jira PCO assignment hygiene digest for Hermes no-agent cron."""

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
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SAFE_FIELDS = ["summary", "status", "priority", "assignee", "updated", "duedate", "issuetype"]
FORBIDDEN_FIELD_HINTS = ["description", "comment", "transcript", "attachment"]
DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_LEAD = "Josica"
SILENT_PREFIX = "[SILENT] PSM Ops automation"
SLACK_USER_ID_RE = re.compile(r"^[UW][A-Z0-9]{2,}$", re.IGNORECASE)
SLACK_USERGROUP_ID_RE = re.compile(r"^S[A-Z0-9]{2,}$", re.IGNORECASE)
SLACK_HANDLE_RE = re.compile(r"^[A-Za-z0-9._-]{1,80}$")


class HygieneError(RuntimeError):
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
        raise HygieneError("PSM_OPS_TIMEZONE must be a valid IANA timezone.") from error


def _parse_as_of(value: str, local_timezone: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(local_timezone)
    raw = value.strip()
    if len(raw) == 10:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as error:
            raise HygieneError("as_of must be ISO date or timestamp.") from error
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=local_timezone)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise HygieneError("as_of must be ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(local_timezone)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a safe PCO assignment hygiene digest.")
    parser.add_argument("--as-of", default="", help="ISO date/timestamp. Defaults to now in Asia/Singapore.")
    parser.add_argument("--dry-run", action="store_true", help="Mark output as a dry run. No writes are ever performed.")
    parser.add_argument("--max-results", type=int, default=100)
    return parser.parse_args(argv)


def _project_key() -> str:
    return _env("PSM_OPS_JIRA_PROJECT_KEY", "PCO") or "PCO"


def _ps_team_field_id() -> str:
    return _env("PSM_OPS_JIRA_FIELD_PS_TEAM") or "customfield_10876"


def _jql_field_ref(field_id: str) -> str:
    match = re.fullmatch(r"customfield_(\d+)", field_id)
    return f"cf[{match.group(1)}]" if match else field_id


def build_jql() -> str:
    ps_team_field = _jql_field_ref(_ps_team_field_id())
    return (
        f"project = {_project_key()} "
        "AND statusCategory != Done "
        f"AND (assignee is EMPTY OR {ps_team_field} is EMPTY OR duedate is EMPTY) "
        "ORDER BY updated DESC"
    )


def _jira_base_url() -> str:
    value = _env("JIRA_BASE_URL", "https://staffany.atlassian.net").rstrip("/")
    if not value:
        raise HygieneError("JIRA_BASE_URL is not configured.")
    return value


def _auth_header() -> str:
    email = _env("JIRA_EMAIL")
    token = _env("JIRA_API_TOKEN")
    if not email or not token:
        raise HygieneError("JIRA_EMAIL and JIRA_API_TOKEN must be configured.")
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
        raise HygieneError(f"Jira API returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise HygieneError(f"Jira API request failed: {error.reason}") from error


def fetch_hygiene_issues(max_results: int) -> list[dict[str, Any]]:
    fields = [*SAFE_FIELDS, _ps_team_field_id()]
    query = urllib.parse.urlencode(
        {
            "jql": build_jql(),
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


def safe_issue(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    key = str(issue.get("key") or "")
    assignee = fields.get("assignee") or {}
    return {
        "key": key,
        "url": f"{_jira_base_url()}/browse/{key}" if key else _jira_base_url(),
        "summary": str(fields.get("summary") or key or "Untitled PCO issue"),
        "status": _field_value(fields.get("status")),
        "priority": _field_value(fields.get("priority")),
        "assignee": _field_value(assignee) if assignee else "Unassigned",
        "due_date": str(fields.get("duedate") or "Not set"),
        "ps_team": _field_value(fields.get(_ps_team_field_id())),
        "updated": str(fields.get("updated") or "Not set"),
    }


def _is_missing(value: Any) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {"", "not set", "none", "null", "unassigned"}


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
        return _slack_escape(label)
    return f"<{safe_url}|{_slack_escape(label)}>"


def _mention_map_path() -> str:
    return _env("PSM_OPS_REMINDER_MENTION_MAP_PATH")


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


def _format_targets(raw_targets: Any) -> list[str]:
    target_list = raw_targets if isinstance(raw_targets, list) else [raw_targets]
    return [
        mention
        for target in target_list
        if isinstance(target, dict)
        for mention in [_format_mention_target(target)]
        if mention
    ]


def load_mention_map() -> tuple[dict[str, list[str]], dict[str, list[str]], str]:
    path = _mention_map_path()
    if not path:
        return {}, {}, ""
    try:
        payload = _load_json_file(path)
    except (OSError, json.JSONDecodeError):
        return {}, {}, "PSM_OPS_REMINDER_MENTION_MAP_PATH could not be read; mentions disabled."
    if not isinstance(payload, dict):
        return {}, {}, "PSM_OPS_REMINDER_MENTION_MAP_PATH has invalid shape; mentions disabled."

    ps_teams_payload = payload.get("ps_teams") if isinstance(payload.get("ps_teams"), dict) else {}
    ps_leads_payload = payload.get("ps_leads") if isinstance(payload.get("ps_leads"), dict) else {}
    ps_teams: dict[str, list[str]] = {}
    ps_leads: dict[str, list[str]] = {}

    for team, targets in ps_teams_payload.items():
        team_name = str(team or "").strip()
        rendered = _format_targets(targets)
        if team_name and rendered:
            ps_teams[team_name] = rendered
    for lead, targets in ps_leads_payload.items():
        lead_name = str(lead or "").strip()
        rendered = _format_targets(targets)
        if lead_name and rendered:
            ps_leads[lead_name] = rendered
    return ps_teams, ps_leads, ""


def load_hygiene_context() -> dict[str, Any]:
    ps_teams, ps_leads, mention_warning = load_mention_map()
    return {
        "ps_teams": ps_teams,
        "ps_leads": ps_leads,
        "mention_warning": mention_warning,
    }


def _format_issue(issue: dict[str, Any]) -> list[str]:
    return [
        f"- {_format_link(issue['url'], issue['key'])} - {_slack_escape(issue['summary'])}",
        (
            f"  Status: {_slack_escape(issue['status'])} | Priority: {_slack_escape(issue['priority'])} | "
            f"Assignee: {_slack_escape(issue['assignee'])} | Due: {_slack_escape(issue['due_date'])} | "
            f"PS Team: {_slack_escape(issue['ps_team'])}"
        ),
    ]


def _needs_lead_triage(issue: dict[str, Any]) -> bool:
    return _is_missing(issue.get("assignee")) or _is_missing(issue.get("ps_team"))


def _needs_due_date(issue: dict[str, Any]) -> bool:
    return _is_missing(issue.get("due_date")) and not _is_missing(issue.get("ps_team"))


def format_digest(
    issues: list[dict[str, Any]],
    as_of: datetime,
    dry_run: bool = False,
    context: dict[str, Any] | None = None,
) -> str:
    today = as_of.date().isoformat()
    if not issues:
        dry = " Dry run." if dry_run else ""
        return f"{SILENT_PREFIX}: no PCO assignment hygiene gaps for {today}.{dry}"

    hygiene_context = context or load_hygiene_context()
    ps_team_mentions = hygiene_context.get("ps_teams") if isinstance(hygiene_context.get("ps_teams"), dict) else {}
    ps_lead_mentions = hygiene_context.get("ps_leads") if isinstance(hygiene_context.get("ps_leads"), dict) else {}
    mention_warning = str(hygiene_context.get("mention_warning") or "").strip()

    lead_triage = [issue for issue in issues if _needs_lead_triage(issue)]
    due_date_issues = [issue for issue in issues if _needs_due_date(issue)]
    due_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in due_date_issues:
        due_by_team[str(issue.get("ps_team") or "Not set")].append(issue)

    dry_label = " DRY RUN" if dry_run else ""
    lines = [
        f"PSM Ops automation: PCO assignment hygiene{dry_label} - {today}",
        "*Source:* Jira PCO safe fields; central digest only",
        f"*Total issues:* {len(issues)}",
    ]

    lead_mentions = ps_lead_mentions.get(DEFAULT_LEAD) or []
    if lead_triage:
        suffix = f" {' '.join(lead_mentions)}" if lead_mentions else ""
        lines.extend(["", f"*Needs PS lead triage: {DEFAULT_LEAD}*{suffix}"])
        for issue in lead_triage:
            lines.extend(_format_issue(issue))
        if not lead_mentions:
            lines.append(f"Lead mention gap: {DEFAULT_LEAD}")

    mention_gaps: list[str] = []
    if due_by_team:
        lines.extend(["", "*Needs due date by PS Team*"])
        for ps_team in sorted(due_by_team):
            mentions = ps_team_mentions.get(ps_team) or []
            suffix = f" {' '.join(mentions)}" if mentions else ""
            lines.extend(["", f"*PS Team: {_slack_escape(ps_team)}*{suffix}"])
            for issue in due_by_team[ps_team]:
                lines.extend(_format_issue(issue))
            if not mentions:
                mention_gaps.append(ps_team)
    if mention_gaps:
        lines.append("")
        lines.append(f"Mention gaps: {_slack_escape(', '.join(sorted(mention_gaps)))}")
    if mention_warning:
        lines.append(f"Mention map warning: {_slack_escape(mention_warning)}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        local_timezone = _timezone()
        as_of = _parse_as_of(args.as_of, local_timezone)
        issues = fetch_hygiene_issues(args.max_results)
        print(format_digest(issues, as_of, args.dry_run))
        return 0
    except HygieneError as error:
        print(
            "\n".join(
                [
                    "PSM Ops automation: PCO assignment hygiene blocked",
                    "Source: Jira PCO",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
