#!/usr/bin/env python3
"""Read-only Slack-context to KER Jira lookup MCP adapter for Launchbot."""

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
SLACK_TIMEOUT_SECONDS = 15
JIRA_TIMEOUT_SECONDS = 30
MAX_THREAD_MESSAGES = 20
MAX_JIRA_RESULTS_PER_QUERY = 10
MAX_RETURNED_CANDIDATES = 5
DEFAULT_ALLOWED_CHANNELS = set()
DEFAULT_JIRA_BASE_URL = "https://staffany.atlassian.net"
KER_RE = re.compile(r"\bKER-\d+\b", re.IGNORECASE)
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"

mcp = FastMCP(
    "launchbot_ker",
    instructions=(
        "Read-only Launchbot adapter that reads bounded Slack thread context "
        "with SLACK_BOT_TOKEN and searches StaffAny Jira KER with JIRA_* env vars. "
        "It never posts Slack messages, mutates Jira, or persists raw transcripts."
    ),
)


class LaunchbotKerError(RuntimeError):
    pass


def _scope(channel_id: str, thread_ts: str, query: str = "") -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "query": query.strip(),
        "project_key": "KER",
        "max_thread_messages": MAX_THREAD_MESSAGES,
        "read_only": True,
        "will_post_message": False,
        "will_mutate_jira": False,
        "transcript_persisted": False,
        "configured_channels_only": False,
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
        "caveat": "Read-only lookup; verify candidate before using it as release truth.",
    }


def _token(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LaunchbotKerError(f"Missing {name}.")
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
        os.environ.get("LAUNCHBOT_KER_ALLOWED_CHANNEL_IDS", "")
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
        raise LaunchbotKerError(_safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotKerError(_safe_error(f"Slack API request failed: {reason}")) from error

    if not payload.get("ok"):
        raise LaunchbotKerError(_safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def _jira_base_url() -> str:
    return (os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_BASE_URL).strip() or DEFAULT_JIRA_BASE_URL).rstrip("/")


def _jira_headers() -> dict[str, str]:
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not email or not token:
        raise LaunchbotKerError("Missing JIRA_EMAIL or JIRA_API_TOKEN.")
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
        raise LaunchbotKerError(_safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotKerError(_safe_error(f"Jira API request failed: {reason}")) from error


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
        raise LaunchbotKerError(_safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotKerError(_safe_error(f"Jira API request failed: {reason}")) from error


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


def _candidate_phrases(text: str, explicit_query: str) -> list[str]:
    combined = f"{explicit_query}\n{text}".lower()
    phrases: list[str] = []
    known_patterns = [
        r"data[- ]?block(?:ing)?",
        r"labor cost",
        r"salary data",
        r"salary information",
        r"permission system",
        r"timesheet approval",
        r"multi[- ]level approval",
    ]
    for pattern in known_patterns:
        if re.search(pattern, combined):
            phrase = re.sub(r"[-\s]+", " ", re.search(pattern, combined).group(0)).strip()
            phrases.append(phrase)
    if explicit_query.strip():
        phrases.insert(0, explicit_query.strip())
    words = [
        word
        for word in re.findall(r"[a-z][a-z0-9]{2,}", combined)
        if word
        not in {
            "the",
            "and",
            "for",
            "this",
            "that",
            "can",
            "you",
            "with",
            "from",
            "are",
            "now",
            "should",
            "currently",
            "working",
            "ticket",
            "board",
            "staffany",
        }
    ]
    for word in words:
        if word not in phrases:
            phrases.append(word)
    deduped: list[str] = []
    for phrase in phrases:
        normalized = re.sub(r"\s+", " ", phrase.strip())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:8]


def _jql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _search_jira_issues(phrases: list[str]) -> list[dict[str, Any]]:
    issues_by_key: dict[str, dict[str, Any]] = {}
    fields = ["summary", "status", "updated", "assignee", "issuetype"]
    for phrase in phrases:
        jql = f'project = KER AND text ~ "{_jql_escape(phrase)}" ORDER BY updated DESC'
        payload = _jira_post(
            "/rest/api/3/search/jql",
            {
                "jql": jql,
                "maxResults": MAX_JIRA_RESULTS_PER_QUERY,
                "fields": fields,
            },
        )
        for issue in payload.get("issues", []) or []:
            if isinstance(issue, dict) and issue.get("key"):
                issue.setdefault("_matched_phrases", [])
                issue["_matched_phrases"].append(phrase)
                issues_by_key.setdefault(issue["key"], issue)
    if len(phrases) >= 2:
        summary_words = [phrase for phrase in phrases if " " not in phrase][:4]
        if len(summary_words) >= 2:
            clauses = [f'summary ~ "{_jql_escape(word)}"' for word in summary_words[:3]]
            payload = _jira_post(
                "/rest/api/3/search/jql",
                {
                    "jql": f"project = KER AND {' AND '.join(clauses)} ORDER BY updated DESC",
                    "maxResults": MAX_JIRA_RESULTS_PER_QUERY,
                    "fields": fields,
                },
            )
            for issue in payload.get("issues", []) or []:
                if isinstance(issue, dict) and issue.get("key"):
                    issue.setdefault("_matched_phrases", [])
                    issue["_matched_phrases"].extend(summary_words[:3])
                    issues_by_key.setdefault(issue["key"], issue)
    return list(issues_by_key.values())


def _issue_to_candidate(issue: dict[str, Any], source_text: str, phrases: list[str]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    summary = str(fields.get("summary") or "")
    status = (fields.get("status") or {}).get("name") or ""
    updated = fields.get("updated") or ""
    assignee = (fields.get("assignee") or {}).get("displayName") or ""
    issue_type = (fields.get("issuetype") or {}).get("name") or ""
    summary_lc = summary.lower()
    source_lc = source_text.lower()
    summary_norm = re.sub(r"[^a-z0-9]+", " ", summary_lc).strip()
    source_norm = re.sub(r"[^a-z0-9]+", " ", source_lc).strip()
    matched = []
    score = 0
    phrase_rank = {phrase: index for index, phrase in enumerate(phrases)}
    for phrase in phrases:
        phrase_lc = phrase.lower()
        phrase_norm = re.sub(r"[^a-z0-9]+", " ", phrase_lc).strip()
        if phrase_norm and phrase_norm in summary_norm:
            if phrase_norm.startswith("data block"):
                score += 14
            else:
                score += 8 if " " in phrase_norm else 4
            matched.append(phrase)
        elif phrase_norm and " " in phrase_norm and all(term in summary_norm for term in phrase_norm.split()):
            score += 6
            matched.append(phrase)
        elif phrase_norm and phrase_norm in source_norm:
            score += 1
    for phrase in issue.get("_matched_phrases", []):
        if phrase not in matched:
            matched.append(phrase)
        score += max(1, 8 - phrase_rank.get(phrase, 7))
    if KER_RE.search(source_text) and issue.get("key", "").upper() in KER_RE.findall(source_text.upper()):
        score += 20
    return {
        "issue_key": issue.get("key") or "",
        "summary": summary,
        "status": status,
        "issue_type": issue_type,
        "assignee": assignee,
        "updated": updated,
        "url": f"{_jira_base_url()}/browse/{issue.get('key')}",
        "matched_terms": matched[:6],
        "score": score,
    }


def _rank_candidates(issues: list[dict[str, Any]], source_text: str, phrases: list[str]) -> list[dict[str, Any]]:
    candidates = [_issue_to_candidate(issue, source_text, phrases) for issue in issues]
    candidates.sort(key=lambda item: (item["score"], item["updated"]), reverse=True)
    return candidates[:MAX_RETURNED_CANDIDATES]


def _slack_reply(candidates: list[dict[str, Any]], confidence: str) -> str:
    if not candidates:
        return "Answer: No matching KER ticket found from this Slack thread.\nConfidence: needs-check"
    top = candidates[0]
    link = f"<{top['url']}|{top['issue_key']}>"
    line = f"Answer: Likely ticket is {link} - {top['summary']} ({top['status']})."
    if len(candidates) > 1 and confidence != "verified":
        alt = ", ".join(f"<{item['url']}|{item['issue_key']}>" for item in candidates[1:3])
        line += f"\nOther candidates: {alt}"
    line += f"\nConfidence: {confidence}"
    return line


@mcp.tool()
def lookup_ker_ticket_by_key(issue_key: str) -> dict[str, Any]:
    """Read one KER issue by key. Safe fields only; no Jira mutation."""

    key = (issue_key or "").strip().upper()
    scope = _scope("", "", key)
    if not KER_RE.fullmatch(key):
        return _blocked("issue_key must look like KER-123.", "Launchbot KER Jira MCP", scope)
    try:
        issue = _jira_get(f"/rest/api/3/issue/{urllib.parse.quote(key)}?fields=summary,status,updated,assignee,issuetype")
    except LaunchbotKerError as error:
        return _blocked(str(error), "Jira issue API", scope)
    candidate = _issue_to_candidate(issue, key, [key])
    return {
        "answer": {
            "candidate": candidate,
            "slack_reply": _slack_reply([candidate], "verified"),
            "will_mutate_jira": False,
        },
        "source": "Jira issue API",
        "scope": scope,
        "confidence": "verified",
        "caveat": "Safe Jira fields only; no comments, descriptions, or attachments returned.",
    }


@mcp.tool()
def find_ker_ticket_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Find likely KER tickets from bounded Slack thread context. Read-only."""

    parsed_channel, parsed_thread_ts, parsed_message_ts = _parse_slack_permalink(slack_permalink)
    channel = (channel_id or parsed_channel).strip()
    current_message_ts = (message_ts or parsed_message_ts).strip()
    thread = (thread_ts or parsed_thread_ts or current_message_ts).strip()
    scope = _scope(channel, thread, query)
    if not channel or not thread:
        return _blocked("channel_id and thread_ts are required, or pass a Slack permalink.", "Launchbot KER Jira MCP", scope)
    try:
        messages = _thread_messages(channel, thread, current_message_ts)
    except LaunchbotKerError as error:
        return _blocked(str(error), "Slack conversations.replies API", scope)

    safe_messages = _safe_messages(messages)
    source_text = "\n".join(message["summary"] for message in safe_messages)
    explicit_keys = sorted({key.upper() for key in KER_RE.findall(f"{query}\n{source_text}")})
    try:
        if explicit_keys:
            issues = [
                _jira_get(f"/rest/api/3/issue/{urllib.parse.quote(key)}?fields=summary,status,updated,assignee,issuetype")
                for key in explicit_keys[:MAX_RETURNED_CANDIDATES]
            ]
            phrases = explicit_keys
        else:
            phrases = _candidate_phrases(source_text, query)
            if not phrases:
                return _needs_check(
                    "Slack thread did not contain enough searchable KER terms.",
                    "Slack conversations.replies API",
                    scope,
                    {"safe_thread_summaries": safe_messages, "will_mutate_jira": False},
                )
            issues = _search_jira_issues(phrases)
    except LaunchbotKerError as error:
        return _blocked(str(error), "Jira search API", scope)

    candidates = _rank_candidates(issues, source_text, phrases)
    confidence = "verified" if len(candidates) == 1 or (candidates and candidates[0]["score"] >= candidates[min(1, len(candidates) - 1)]["score"] + 4) else "needs-check"
    return {
        "answer": {
            "candidates": candidates,
            "top_candidate": candidates[0] if candidates else None,
            "search_terms": phrases,
            "safe_thread_summaries": safe_messages,
            "slack_reply": _slack_reply(candidates, confidence),
            "will_mutate_jira": False,
            "will_post_message": False,
            "transcript_persisted": False,
        },
        "source": "Slack conversations.replies API + Jira KER search API",
        "scope": scope,
        "confidence": confidence,
        "caveat": "Read-only lookup over safe Jira fields; verify before treating as release truth.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
