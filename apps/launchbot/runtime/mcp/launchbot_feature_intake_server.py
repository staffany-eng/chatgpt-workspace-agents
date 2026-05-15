#!/usr/bin/env python3
"""Guarded Slack-thread to Jira Product Discovery intake MCP adapter for Launchbot."""

from __future__ import annotations

import base64
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from profile_env import load_profile_env


load_profile_env()

SLACK_API_BASE_URL = "https://slack.com/api/"
SLACK_WORKSPACE_BASE_URL = "https://staffany.slack.com"
SLACK_TIMEOUT_SECONDS = 15
JIRA_TIMEOUT_SECONDS = 30
MAX_THREAD_MESSAGES = 20
MAX_DESCRIPTION_MESSAGES = 8
DEFAULT_ALLOWED_CHANNELS = {"C0B32M34J3W", "CF8PK6V4J"}
DEFAULT_JIRA_BASE_URL = "https://staffany.atlassian.net"
KER_PROJECT_KEY = "KER"
KER_IDEA_ISSUE_TYPE_ID = "10043"
SLACK_PRD_FIELD_ID = "customfield_10080"
PRODUCT_AREA_FIELD_ID = "customfield_10081"
PRODUCT_LEAD_FIELD_ID = "customfield_10087"
PRODUCT_AREA_INTERNAL_AI_TOOLS_ID = "11370"
PRODUCT_LEAD_KY_ID = "10091"
CONFIRMATION_PHRASES = {"create intake", "create ker intake"}
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"

mcp = FastMCP(
    "launchbot_feature_intake",
    instructions=(
        "Guarded Launchbot adapter that reads bounded Slack thread context with "
        "SLACK_BOT_TOKEN and creates Jira Product Discovery KER ideas only after "
        "explicit confirmation. It never sends Slack messages, comments on Jira, "
        "transitions Jira issues, or persists raw Slack transcripts."
    ),
)


class LaunchbotFeatureIntakeError(RuntimeError):
    pass


def _scope(channel_id: str, thread_ts: str, slack_permalink: str = "") -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "slack_permalink": slack_permalink,
        "project_key": KER_PROJECT_KEY,
        "issue_type_id": KER_IDEA_ISSUE_TYPE_ID,
        "max_thread_messages": MAX_THREAD_MESSAGES,
        "will_post_message": False,
        "transcript_persisted": False,
        "configured_channels_only": True,
        "requires_confirmation": True,
    }


def _blocked(message: str, source: str, scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": message,
        "source": source,
        "scope": scope,
        "confidence": "blocked",
        "caveat": "No Slack post or Jira mutation was performed.",
    }


def _needs_check(message: str, source: str, scope: dict[str, Any], details: dict[str, Any] | None = None) -> dict[str, Any]:
    answer: dict[str, Any] = {"message": message}
    if details:
        answer.update(details)
    return {
        "answer": answer,
        "source": source,
        "scope": scope,
        "confidence": "needs-check",
        "caveat": "Preview only; confirm with `create intake` before Launchbot creates a KER idea.",
    }


def _token(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LaunchbotFeatureIntakeError(f"Missing {name}.")
    return value


def _safe_error(message: str) -> str:
    safe = str(message)
    for name in ("SLACK_BOT_TOKEN", "JIRA_API_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            safe = safe.replace(value, f"[REDACTED_{name}]")
    return safe[:350]


def _configured_channel_ids() -> set[str]:
    raw = (
        os.environ.get("LAUNCHBOT_FEATURE_INTAKE_ALLOWED_CHANNEL_IDS", "")
        or os.environ.get("SLACK_ALLOWED_CHANNEL_IDS", "")
        or os.environ.get("SLACK_ALLOWED_CHANNELS", "")
        or os.environ.get("SLACK_HOME_CHANNEL", "")
    )
    configured = {value for value in re.split(r"[\s,]+", raw.strip()) if value}
    return configured or set(DEFAULT_ALLOWED_CHANNELS)


def _parse_slack_permalink(permalink: str) -> tuple[str, str, str]:
    match = re.search(r"/archives/([A-Z0-9]+)/p(\d{10})(\d{6})", permalink or "")
    if not match:
        return "", "", ""
    message_ts = f"{match.group(2)}.{match.group(3)}"
    parsed = urllib.parse.urlparse(permalink)
    query = urllib.parse.parse_qs(parsed.query)
    thread_ts = (query.get("thread_ts") or [""])[0] or message_ts
    return match.group(1), thread_ts, message_ts


def _slack_ts_to_permalink_ts(ts: str) -> str:
    digits = re.sub(r"[^0-9]", "", ts or "")
    return digits if len(digits) >= 16 else ""


def _source_permalink(channel_id: str, thread_ts: str, message_ts: str, slack_permalink: str) -> str:
    if slack_permalink.strip():
        return slack_permalink.strip()
    permalink_ts = _slack_ts_to_permalink_ts(message_ts or thread_ts)
    if not channel_id or not permalink_ts:
        return ""
    query = f"?thread_ts={urllib.parse.quote(thread_ts)}&cid={urllib.parse.quote(channel_id)}" if thread_ts else ""
    return f"{SLACK_WORKSPACE_BASE_URL}/archives/{channel_id}/p{permalink_ts}{query}"


def _slack_api(method: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = urllib.parse.urljoin(SLACK_API_BASE_URL, method)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {_token('SLACK_BOT_TOKEN')}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=SLACK_TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotFeatureIntakeError(_safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotFeatureIntakeError(_safe_error(f"Slack API request failed: {reason}")) from error

    if not payload.get("ok"):
        raise LaunchbotFeatureIntakeError(_safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def _jira_base_url() -> str:
    return (os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_BASE_URL).strip() or DEFAULT_JIRA_BASE_URL).rstrip("/")


def _jira_headers() -> dict[str, str]:
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not email or not token:
        raise LaunchbotFeatureIntakeError("Missing JIRA_EMAIL or JIRA_API_TOKEN.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def _jira_get(path: str) -> dict[str, Any]:
    request = urllib.request.Request(f"{_jira_base_url()}{path}", headers=_jira_headers(), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=JIRA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotFeatureIntakeError(_safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotFeatureIntakeError(_safe_error(f"Jira API request failed: {reason}")) from error


def _jira_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{_jira_base_url()}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers=_jira_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=JIRA_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotFeatureIntakeError(_safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotFeatureIntakeError(_safe_error(f"Jira API request failed: {reason}")) from error


def _safe_text(value: str) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"<@[^>]+>", "<@user>", text)
    text = re.sub(r"<#[^>]+>", "<#channel>", text)
    text = re.sub(r"<(https?://[^>|]+)(?:\|[^>]+)?>", r"\1", text)
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[phone]", text)
    text = re.sub(r"\s+", " ", text)
    return text[:500]


def _ts_float(value: str | float | int | None, default: float = 0.0) -> float:
    try:
        return float(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def _thread_messages(channel_id: str, thread_ts: str, latest_ts: str = "") -> list[dict[str, Any]]:
    payload = _slack_api(
        "conversations.replies",
        {
            "channel": channel_id,
            "ts": thread_ts,
            "limit": MAX_THREAD_MESSAGES,
            "inclusive": "true",
        },
    )
    messages = [item for item in payload.get("messages", []) if isinstance(item, dict)]
    latest = _ts_float(latest_ts, 0.0)
    if latest > 0:
        messages = [message for message in messages if _ts_float(message.get("ts"), 0.0) <= latest]
    return messages


def _safe_messages(messages: list[dict[str, Any]]) -> list[dict[str, str]]:
    safe: list[dict[str, str]] = []
    for message in messages:
        safe.append(
            {
                "ts": str(message.get("ts") or ""),
                "user_id": str(message.get("user") or message.get("bot_id") or ""),
                "summary": _safe_text(str(message.get("text") or "")),
            }
        )
    return safe


def _plain_thread_text(safe_messages: list[dict[str, str]]) -> str:
    return "\n".join(message["summary"] for message in safe_messages if message.get("summary"))


def _is_launchbot_intake_automation(text: str) -> bool:
    lowered = text.lower()
    return (
        ("launch bot" in lowered or "launchbot" in lowered or "centralized product bot" in lowered)
        and ("feature request" in lowered or "intake" in lowered)
        and ("automated" in lowered or "upgrade" in lowered or "recreating this from notes" in lowered)
    )


def _title_case_summary(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip(" -:,."))
    if not cleaned:
        return "Feature request from Slack thread"
    cleaned = cleaned[0].upper() + cleaned[1:]
    return cleaned[:180]


def _proposed_summary(safe_messages: list[dict[str, str]], explicit_summary: str = "") -> str:
    if explicit_summary.strip():
        return _title_case_summary(explicit_summary)
    text = _plain_thread_text(safe_messages)
    if _is_launchbot_intake_automation(text):
        return "Automate Slack feature request intake into Jira Product Discovery"
    for message in safe_messages:
        summary = message.get("summary", "")
        if len(summary) >= 18 and not re.fullmatch(r"(?i)(yes|yeah|ok|okay|done|thanks|thank you)[.! ]*", summary):
            summary = re.sub(r"(?i)\b(can you|could you|pls|please|help me|intake this|create this)\b", "", summary)
            return _title_case_summary(summary)
    return "Feature request from Slack thread"


def _adf_paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "content": [{"type": "text", "text": text[:1200]}]}


def _adf_heading(text: str, level: int = 3) -> dict[str, Any]:
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text[:200]}]}


def _description_adf(source_url: str, safe_messages: list[dict[str, str]], summary: str) -> dict[str, Any]:
    snippets = [message["summary"] for message in safe_messages[:MAX_DESCRIPTION_MESSAGES] if message.get("summary")]
    captured = "\n".join(f"- {snippet}" for snippet in snippets) or "- No readable Slack text captured."
    return {
        "type": "doc",
        "version": 1,
        "content": [
            _adf_heading("Source"),
            _adf_paragraph(source_url),
            _adf_heading("Intake Summary"),
            _adf_paragraph(summary),
            _adf_heading("Captured Slack Context"),
            _adf_paragraph(captured),
            _adf_heading("Triage Notes"),
            _adf_paragraph("Needs product triage. Launchbot captured this from Slack and did not infer priority, roadmap, or release timing."),
        ],
    }


def _jql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _dedupe_tokens(source_url: str) -> list[str]:
    tokens = []
    match = re.search(r"/p(\d{10,16})", source_url)
    if match:
        tokens.append(match.group(1))
    for item in re.findall(r"thread_ts=([0-9.]+)|cid=([A-Z0-9]+)", source_url):
        token = next(value for value in item if value)
        tokens.append(token)
    return [token for token in tokens if token]


def _issue_candidate(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    status = fields.get("status") or {}
    return {
        "issue_key": issue.get("key") or "",
        "summary": fields.get("summary") or "",
        "status": status.get("name") or "",
        "url": f"{_jira_base_url()}/browse/{issue.get('key')}",
        "slack_prd": fields.get(SLACK_PRD_FIELD_ID) or "",
    }


def _find_duplicate(source_url: str, summary: str) -> dict[str, Any] | None:
    fields = ["summary", "status", SLACK_PRD_FIELD_ID]
    issues: list[dict[str, Any]] = []
    for token in _dedupe_tokens(source_url)[:3]:
        payload = _jira_post(
            "/rest/api/3/search/jql",
            {
                "jql": f'project = {KER_PROJECT_KEY} AND text ~ "{_jql_escape(token)}" ORDER BY updated DESC',
                "maxResults": 10,
                "fields": fields,
            },
        )
        issues.extend([issue for issue in payload.get("issues", []) or [] if isinstance(issue, dict)])
    if summary:
        payload = _jira_post(
            "/rest/api/3/search/jql",
            {
                "jql": f'project = {KER_PROJECT_KEY} AND summary ~ "{_jql_escape(summary[:80])}" ORDER BY updated DESC',
                "maxResults": 5,
                "fields": fields,
            },
        )
        issues.extend([issue for issue in payload.get("issues", []) or [] if isinstance(issue, dict)])

    seen: set[str] = set()
    for issue in issues:
        key = issue.get("key")
        if not key or key in seen:
            continue
        seen.add(key)
        candidate = _issue_candidate(issue)
        if candidate["slack_prd"] == source_url:
            return candidate
    return None


def _proposed_fields(source_url: str, safe_messages: list[dict[str, str]], summary: str, reporter_account_id: str = "") -> dict[str, Any]:
    fields: dict[str, Any] = {
        "project": {"key": KER_PROJECT_KEY},
        "issuetype": {"id": KER_IDEA_ISSUE_TYPE_ID},
        "summary": summary,
        SLACK_PRD_FIELD_ID: source_url,
        "description": _description_adf(source_url, safe_messages, summary),
    }
    if reporter_account_id:
        fields["reporter"] = {"id": reporter_account_id}
    if _is_launchbot_intake_automation(_plain_thread_text(safe_messages)):
        fields[PRODUCT_AREA_FIELD_ID] = [{"id": PRODUCT_AREA_INTERNAL_AI_TOOLS_ID}]
        fields[PRODUCT_LEAD_FIELD_ID] = [{"id": PRODUCT_LEAD_KY_ID}]
    return fields


def _preview(
    channel_id: str,
    thread_ts: str,
    message_ts: str,
    slack_permalink: str,
    summary_override: str = "",
) -> dict[str, Any]:
    parsed_channel, parsed_thread_ts, parsed_message_ts = _parse_slack_permalink(slack_permalink)
    channel = (channel_id or parsed_channel).strip()
    current_message_ts = (message_ts or parsed_message_ts).strip()
    thread = (thread_ts or parsed_thread_ts or current_message_ts).strip()
    source_url = _source_permalink(channel, thread, current_message_ts, slack_permalink)
    scope = _scope(channel, thread, source_url)
    if not channel or not thread:
        return _blocked("channel_id and thread_ts are required, or pass a Slack permalink.", "Launchbot feature intake MCP", scope)
    if channel not in _configured_channel_ids():
        return _blocked("Launchbot feature intake is restricted to configured channel IDs.", "Launchbot feature intake MCP", scope)
    if not source_url.startswith("https://"):
        return _blocked("A Slack permalink is required so Jira Slack / PRD can be the idempotency key.", "Launchbot feature intake MCP", scope)

    try:
        messages = _thread_messages(channel, thread, current_message_ts)
    except LaunchbotFeatureIntakeError as error:
        return _blocked(str(error), "Slack conversations.replies API", scope)

    safe_messages = _safe_messages(messages)
    summary = _proposed_summary(safe_messages, summary_override)
    proposed_fields = _proposed_fields(source_url, safe_messages, summary)
    try:
        duplicate = _find_duplicate(source_url, summary)
    except LaunchbotFeatureIntakeError as error:
        return _blocked(str(error), "Jira duplicate search API", scope)

    slack_reply = (
        "Launchbot automation: Previewed KER intake.\n"
        f"Summary: {summary}\n"
        f"Source: {source_url}\n"
        f"Duplicate: {duplicate['issue_key'] if duplicate else 'none found'}\n"
        "Confirm with `create intake` to create it."
    )
    return {
        "answer": {
            "summary": summary,
            "source_permalink": source_url,
            "duplicate": duplicate,
            "proposed_fields": proposed_fields,
            "safe_thread_summaries": safe_messages,
            "slack_reply": slack_reply,
            "will_mutate_jira": False,
            "will_post_message": False,
            "transcript_persisted": False,
            "required_confirmation": "create intake",
        },
        "source": "Slack conversations.replies API + Jira duplicate search API",
        "scope": scope,
        "confidence": "needs-check" if duplicate else "verified",
        "caveat": "Preview only; no Jira idea was created.",
    }


@mcp.tool()
def preview_feature_intake_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    summary_override: str = "",
) -> dict[str, Any]:
    """Preview a Jira Product Discovery KER intake from bounded Slack thread context. No mutation."""

    return _preview(channel_id, thread_ts, message_ts, slack_permalink, summary_override)


@mcp.tool()
def create_feature_intake_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    summary_override: str = "",
    confirmation: str = "",
) -> dict[str, Any]:
    """Create one KER idea from Slack context after explicit confirmation."""

    parsed_channel, parsed_thread_ts, parsed_message_ts = _parse_slack_permalink(slack_permalink)
    channel = (channel_id or parsed_channel).strip()
    current_message_ts = (message_ts or parsed_message_ts).strip()
    thread = (thread_ts or parsed_thread_ts or current_message_ts).strip()
    source_url = _source_permalink(channel, thread, current_message_ts, slack_permalink)
    scope = _scope(channel, thread, source_url)
    scope["will_mutate_jira"] = True
    if confirmation.strip().lower() not in CONFIRMATION_PHRASES:
        return _blocked("Confirmation must be exactly `create intake` or `create KER intake`.", "Launchbot feature intake MCP", scope)

    preview = _preview(channel, thread, current_message_ts, source_url, summary_override)
    if preview.get("confidence") == "blocked":
        return preview
    answer = preview.get("answer") or {}
    duplicate = answer.get("duplicate")
    if duplicate:
        return {
            "answer": {
                "issue": duplicate,
                "created": False,
                "slack_reply": (
                    "Launchbot automation: Existing KER intake found. "
                    f"<{duplicate['url']}|{duplicate['issue_key']}> - {duplicate['summary']}"
                ),
                "will_mutate_jira": False,
                "will_post_message": False,
                "transcript_persisted": False,
            },
            "source": "Jira duplicate search API",
            "scope": scope,
            "confidence": "verified",
            "caveat": "Same Slack source already has a KER idea; no duplicate was created.",
        }

    try:
        myself = _jira_get("/rest/api/3/myself")
        reporter_account_id = str(myself.get("accountId") or "")
        fields = _proposed_fields(
            answer["source_permalink"],
            answer.get("safe_thread_summaries") or [],
            answer["summary"],
            reporter_account_id,
        )
        created = _jira_post("/rest/api/3/issue?notifyUsers=false", {"fields": fields})
    except LaunchbotFeatureIntakeError as error:
        return _blocked(str(error), "Jira create issue API", scope)

    issue_key = created.get("key") or ""
    issue_url = f"{_jira_base_url()}/browse/{issue_key}" if issue_key else ""
    return {
        "answer": {
            "issue": {
                "issue_key": issue_key,
                "summary": answer["summary"],
                "url": issue_url,
                "slack_prd": answer["source_permalink"],
            },
            "created": True,
            "slack_reply": (
                "Launchbot automation: Created KER intake "
                f"<{issue_url}|{issue_key}> - {answer['summary']}"
            ),
            "will_mutate_jira": True,
            "will_post_message": False,
            "transcript_persisted": False,
        },
        "source": "Slack conversations.replies API + Jira create issue API",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Created one Jira Product Discovery idea only; no transition, comment, assignment, or Slack post was performed by the MCP.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
