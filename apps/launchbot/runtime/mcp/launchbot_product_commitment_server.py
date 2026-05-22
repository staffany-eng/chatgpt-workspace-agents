#!/usr/bin/env python3
"""Read-only Slack-thread to Jira product commitment checker for Launchbot."""

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
MAX_JIRA_RESULTS_PER_QUERY = 10
MAX_RETURNED_CANDIDATES = 5
DEFAULT_ALLOWED_CHANNELS = set()
DEFAULT_JIRA_BASE_URL = "https://staffany.atlassian.net"
KER_PROJECT_KEY = "KER"
SLACK_PRD_FIELD_ID = "customfield_10080"
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"

mcp = FastMCP(
    "launchbot_product_commitment",
    instructions=(
        "Read-only Launchbot adapter that reads bounded Slack thread context "
        "with SLACK_BOT_TOKEN, searches StaffAny Jira KER/JPD with JIRA_* env vars, "
        "and reports only explicit reviewed Jira commitment evidence. It never posts "
        "Slack messages, mutates Jira, persists raw transcripts, or estimates timelines. "
        "Callers must return answer.slack_reply verbatim and must not add sprint, priority, "
        "assignee, unassigned, issue-status, backlog, no-fix-version, or last-updated commentary "
        "as commitment evidence. Callers must call this tool fresh for every commitment request "
        "and must not answer from earlier Slack replies."
    ),
)


class LaunchbotProductCommitmentError(RuntimeError):
    pass


def _scope(channel_id: str, thread_ts: str, slack_permalink: str = "", query: str = "") -> dict[str, Any]:
    return {
        "channel_id": channel_id,
        "thread_ts": thread_ts,
        "slack_permalink": slack_permalink.strip(),
        "query": query.strip(),
        "project_key": KER_PROJECT_KEY,
        "max_thread_messages": MAX_THREAD_MESSAGES,
        "read_only": True,
        "commitment_check_only": True,
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
        "caveat": "No Slack post, Jira mutation, intake creation, or timeline estimate was performed.",
    }


def _token(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise LaunchbotProductCommitmentError(f"Missing {name}.")
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
        os.environ.get("LAUNCHBOT_PRODUCT_COMMITMENT_ALLOWED_CHANNEL_IDS", "")
        or os.environ.get("SLACK_ALLOWED_CHANNEL_IDS", "")
        or os.environ.get("SLACK_ALLOWED_CHANNELS", "")
        or os.environ.get("SLACK_HOME_CHANNEL", "")
    )
    configured = {value for value in re.split(r"[\s,]+", raw.strip()) if value}
    return configured or set(DEFAULT_ALLOWED_CHANNELS)


def _configured_commitment_field_ids() -> list[str]:
    raw = os.environ.get("LAUNCHBOT_PRODUCT_COMMITMENT_FIELD_IDS", "")
    return [
        value
        for value in re.split(r"[\s,]+", raw.strip())
        if re.fullmatch(r"customfield_\d+", value)
    ]


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
        raise LaunchbotProductCommitmentError(_safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotProductCommitmentError(_safe_error(f"Slack API request failed: {reason}")) from error

    if not payload.get("ok"):
        raise LaunchbotProductCommitmentError(_safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def _jira_base_url() -> str:
    return (os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_BASE_URL).strip() or DEFAULT_JIRA_BASE_URL).rstrip("/")


def _jira_headers() -> dict[str, str]:
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not email or not token:
        raise LaunchbotProductCommitmentError("Missing JIRA_EMAIL or JIRA_API_TOKEN.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


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
        raise LaunchbotProductCommitmentError(_safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotProductCommitmentError(_safe_error(f"Jira API request failed: {reason}")) from error


def _safe_text(value: str) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"<!subteam\^[^>]+>", "<!subteam>", text)
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
        if message.get("bot_id") or message.get("subtype") == "bot_message":
            continue
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


def _topic_hint(source_text: str, query: str = "") -> str:
    text = f"{query}\n{source_text}".lower()
    if re.search(r"payslip\s+(?:to\s+)?email|email\s+payslip", text):
        return "payslip-to-email"
    words = [
        word
        for word in re.findall(r"[a-z][a-z0-9]{2,}", text)
        if word
        not in {
            "subteam",
            "there",
            "any",
            "plan",
            "build",
            "function",
            "long",
            "might",
            "take",
            "not",
            "committed",
            "roadmap",
            "iirc",
            "check",
            "user",
            "thread",
            "this",
            "that",
            "with",
            "staffany",
        }
    ]
    return "-".join(words[:4]) if words else "this-product-request"


def _candidate_phrases(text: str, explicit_query: str) -> list[str]:
    combined = f"{explicit_query}\n{text}".lower()
    phrases: list[str] = []
    known_patterns = [
        r"payslip\s+to\s+email",
        r"payslip\s+email",
        r"email\s+payslip",
        r"payslip",
        r"roadmap",
        r"commit(?:ted|ment)?",
    ]
    for pattern in known_patterns:
        match = re.search(pattern, combined)
        if match:
            phrases.append(re.sub(r"\s+", " ", match.group(0)).strip())
    if explicit_query.strip():
        phrases.insert(0, explicit_query.strip())
    stop_words = {
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
        "there",
        "any",
        "plan",
        "build",
        "function",
        "long",
        "might",
        "take",
        "not",
        "committed",
        "roadmap",
        "iirc",
        "check",
        "staffany",
        "subteam",
        "user",
    }
    words = [word for word in re.findall(r"[a-z][a-z0-9]{2,}", combined) if word not in stop_words]
    for size in (3, 2):
        for index in range(0, max(0, len(words) - size + 1)):
            phrases.append(" ".join(words[index : index + size]))
    phrases.extend(words)
    deduped: list[str] = []
    for phrase in phrases:
        normalized = re.sub(r"\s+", " ", phrase.strip())
        if normalized and normalized not in deduped:
            deduped.append(normalized)
    return deduped[:10]


def _jql_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _search_fields(commitment_field_ids: list[str]) -> list[str]:
    fields = [
        "summary",
        "status",
        "updated",
        "assignee",
        "issuetype",
        "fixVersions",
        SLACK_PRD_FIELD_ID,
    ]
    for field_id in commitment_field_ids:
        if field_id not in fields:
            fields.append(field_id)
    return fields


def _dedupe_tokens(source_url: str) -> list[str]:
    tokens = []
    match = re.search(r"/p(\d{10,16})", source_url)
    if match:
        tokens.append(match.group(1))
    for item in re.findall(r"thread_ts=([0-9.]+)|cid=([A-Z0-9]+)", source_url):
        token = next(value for value in item if value)
        tokens.append(token)
    return [token for token in tokens if token]


def _search_jira_issues(phrases: list[str], source_url: str, commitment_field_ids: list[str]) -> list[dict[str, Any]]:
    issues_by_key: dict[str, dict[str, Any]] = {}
    fields = _search_fields(commitment_field_ids)
    for token in _dedupe_tokens(source_url)[:3]:
        payload = _jira_post(
            "/rest/api/3/search/jql",
            {
                "jql": f'project = {KER_PROJECT_KEY} AND text ~ "{_jql_escape(token)}" ORDER BY updated DESC',
                "maxResults": MAX_JIRA_RESULTS_PER_QUERY,
                "fields": fields,
            },
        )
        for issue in payload.get("issues", []) or []:
            if isinstance(issue, dict) and issue.get("key"):
                issue.setdefault("_matched_phrases", [])
                issue["_matched_phrases"].append("slack source")
                issues_by_key.setdefault(issue["key"], issue)
    for phrase in phrases:
        jql = f'project = {KER_PROJECT_KEY} AND text ~ "{_jql_escape(phrase)}" ORDER BY updated DESC'
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
    return list(issues_by_key.values())


def _field_value_text(value: Any) -> str:
    if value in (None, "", [], {}):
        return ""
    if isinstance(value, dict):
        return str(value.get("value") or value.get("name") or value.get("displayName") or value.get("id") or "").strip()
    if isinstance(value, list):
        parts = [_field_value_text(item) for item in value]
        return "; ".join(part for part in parts if part)
    return str(value).strip()


def _fix_version_evidence(fix_versions: Any) -> list[dict[str, Any]]:
    if not isinstance(fix_versions, list):
        return []
    evidence = []
    for version in fix_versions:
        if not isinstance(version, dict):
            continue
        name = str(version.get("name") or "").strip()
        if not name:
            continue
        release_date = str(version.get("releaseDate") or "").strip()
        released = version.get("released")
        details = name
        if release_date:
            details = f"{details} ({release_date})"
        elif released is True:
            details = f"{details} (released)"
        evidence.append(
            {
                "field": "fixVersions",
                "field_label": "Fix versions",
                "value": details,
                "review_status": "standard_jira_field",
            }
        )
    return evidence


def _commitment_evidence(issue: dict[str, Any], commitment_field_ids: list[str]) -> list[dict[str, Any]]:
    fields = issue.get("fields") or {}
    evidence = _fix_version_evidence(fields.get("fixVersions"))
    for field_id in commitment_field_ids:
        value = _field_value_text(fields.get(field_id))
        if value:
            evidence.append(
                {
                    "field": field_id,
                    "field_label": field_id,
                    "value": value,
                    "review_status": "configured_reviewed_field",
                }
            )
    return evidence


def _issue_to_candidate(issue: dict[str, Any], source_text: str, phrases: list[str], source_url: str, commitment_field_ids: list[str]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    summary = str(fields.get("summary") or "")
    status = (fields.get("status") or {}).get("name") or ""
    updated = fields.get("updated") or ""
    assignee = (fields.get("assignee") or {}).get("displayName") or ""
    issue_type = (fields.get("issuetype") or {}).get("name") or ""
    slack_prd = str(fields.get(SLACK_PRD_FIELD_ID) or "")
    summary_norm = re.sub(r"[^a-z0-9]+", " ", summary.lower()).strip()
    source_norm = re.sub(r"[^a-z0-9]+", " ", source_text.lower()).strip()
    matched = []
    score = 0
    if slack_prd and slack_prd == source_url:
        score += 40
        matched.append("slack source")
    for phrase in phrases:
        phrase_norm = re.sub(r"[^a-z0-9]+", " ", phrase.lower()).strip()
        if phrase_norm and phrase_norm in summary_norm:
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
        score += 3
    evidence = _commitment_evidence(issue, commitment_field_ids)
    if evidence:
        score += 6
    return {
        "issue_key": issue.get("key") or "",
        "summary": summary,
        "status": status,
        "issue_type": issue_type,
        "assignee": assignee,
        "updated": updated,
        "url": f"{_jira_base_url()}/browse/{issue.get('key')}",
        "matched_terms": matched[:6],
        "commitment_evidence": evidence,
        "score": score,
    }


def _rank_candidates(
    issues: list[dict[str, Any]],
    source_text: str,
    phrases: list[str],
    source_url: str,
    commitment_field_ids: list[str],
) -> list[dict[str, Any]]:
    candidates = [_issue_to_candidate(issue, source_text, phrases, source_url, commitment_field_ids) for issue in issues]
    candidates.sort(key=lambda item: (bool(item["commitment_evidence"]), item["score"], item["updated"]), reverse=True)
    return candidates[:MAX_RETURNED_CANDIDATES]


def _answer_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence = candidate.get("commitment_evidence") or []
    answer_candidate = {
        "issue_key": candidate.get("issue_key") or "",
        "summary": candidate.get("summary") or "",
        "url": candidate.get("url") or "",
        "matched_terms": candidate.get("matched_terms") or [],
        "commitment_evidence": evidence,
        "has_reviewed_commitment_evidence": bool(evidence),
    }
    if evidence:
        answer_candidate["status"] = candidate.get("status") or ""
    else:
        answer_candidate["non_commitment_fields_redacted"] = True
    return answer_candidate


def _answer_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_answer_candidate(candidate) for candidate in candidates]


def _commitment_reply(topic: str, candidates: list[dict[str, Any]], channel_id: str, thread_ts: str) -> tuple[str, str]:
    if not candidates:
        return (
            f"Answer: No matching KER/JPD issue found for {topic} yet.\n"
            "Source: Slack thread + Jira KER read-only search\n"
            f"Scope: {channel_id} / {thread_ts}\n"
            "Confidence: needs-check\n"
            "Caveat: I can only confirm commitments from reviewed Jira/KER fields; no ETA was inferred.",
            "needs-check",
        )
    top = candidates[0]
    evidence = top.get("commitment_evidence") or []
    if evidence:
        first = evidence[0]
        return (
            f"Answer: Commitment evidence found in <{top['url']}|{top['issue_key']}> - {top['summary']} ({top['status']}).\n"
            f"Commitment: {first['field_label']} = {first['value']}\n"
            "Source: Slack thread + Jira KER read-only search\n"
            f"Scope: {channel_id} / {thread_ts}\n"
            "Confidence: verified\n"
            "Caveat: I only confirmed explicit reviewed Jira commitment fields; no ETA was inferred beyond Jira.",
            "verified",
        )
    return (
        f"Answer: No committed Jira roadmap evidence found for {topic} yet.\n"
        "Source: Slack thread + Jira KER read-only search\n"
        f"Scope: {channel_id} / {thread_ts}\n"
        "Confidence: needs-check\n"
        "Caveat: I can only confirm commitments from reviewed Jira/KER fields; no ETA was inferred.",
        "needs-check",
    )


@mcp.tool()
def check_product_commitment_from_slack_thread(
    channel_id: str = "",
    thread_ts: str = "",
    message_ts: str = "",
    slack_permalink: str = "",
    query: str = "",
) -> dict[str, Any]:
    """Check explicit Jira KER/JPD commitment evidence from bounded Slack thread context.

    Read-only. Return answer.slack_reply verbatim in Slack-facing answers; do not add
    sprint, priority, assignee, unassigned, issue-status, backlog, no-fix-version, or
    last-updated commentary. Call this tool fresh for every commitment request.
    """

    parsed_channel, parsed_thread_ts, parsed_message_ts = _parse_slack_permalink(slack_permalink)
    channel = (channel_id or parsed_channel).strip()
    current_message_ts = (message_ts or parsed_message_ts).strip()
    thread = (thread_ts or parsed_thread_ts or current_message_ts).strip()
    source_url = _source_permalink(channel, thread, current_message_ts, slack_permalink)
    scope = _scope(channel, thread, source_url, query)
    if not channel or not thread:
        return _blocked("channel_id and thread_ts are required, or pass a Slack permalink.", "Launchbot product commitment MCP", scope)
    try:
        messages = _thread_messages(channel, thread, current_message_ts)
    except LaunchbotProductCommitmentError as error:
        return _blocked(str(error), "Slack conversations.replies API", scope)

    safe_messages = _safe_messages(messages)
    source_text = _plain_thread_text(safe_messages)
    topic = _topic_hint(source_text, query)
    phrases = _candidate_phrases(source_text, query)
    if not phrases:
        reply, confidence = _commitment_reply(topic, [], channel, thread)
        return {
            "answer": {
                "topic": topic,
                "candidates": [],
                "top_candidate": None,
                "search_terms": [],
                "safe_thread_summaries": safe_messages,
                "slack_reply": reply,
                "will_mutate_jira": False,
                "will_post_message": False,
                "transcript_persisted": False,
            },
            "source": "Slack conversations.replies API",
            "scope": scope,
            "confidence": confidence,
            "caveat": "No Jira mutation, intake creation, or timeline estimate was performed.",
        }

    commitment_field_ids = _configured_commitment_field_ids()
    try:
        issues = _search_jira_issues(phrases, source_url, commitment_field_ids)
    except LaunchbotProductCommitmentError as error:
        return _blocked(str(error), "Jira KER/JPD search API", scope)

    candidates = _rank_candidates(issues, source_text, phrases, source_url, commitment_field_ids)
    reply, confidence = _commitment_reply(topic, candidates, channel, thread)
    answer_candidates = _answer_candidates(candidates)
    return {
        "answer": {
            "topic": topic,
            "candidates": answer_candidates,
            "top_candidate": answer_candidates[0] if answer_candidates else None,
            "search_terms": phrases,
            "reviewed_commitment_fields": ["fixVersions", *commitment_field_ids],
            "safe_thread_summaries": safe_messages,
            "slack_reply": reply,
            "will_mutate_jira": False,
            "will_post_message": False,
            "transcript_persisted": False,
            "will_create_intake": False,
            "will_estimate_timeline": False,
        },
        "source": "Slack conversations.replies API + Jira KER read-only search API",
        "scope": scope,
        "confidence": confidence,
        "caveat": "Only explicit reviewed Jira commitment fields count; no ETA was inferred.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
