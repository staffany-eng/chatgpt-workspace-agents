#!/usr/bin/env python3
"""Preview-first HubSpot-to-IFI tracking MCP adapter for Launchbot."""

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

JIRA_TIMEOUT_SECONDS = 30
HUBSPOT_TIMEOUT_SECONDS = 30
DEFAULT_JIRA_BASE_URL = "https://staffany.atlassian.net"
DEFAULT_HUBSPOT_PORTAL_ID = "4137076"
DEFAULT_IFI_PROJECT_KEY = "IFI"
DEFAULT_IFI_ISSUE_TYPE_ID = "10151"
DEFAULT_HUBSPOT_COMPANY_ID_FIELD_ID = "customfield_10881"
DEFAULT_HUBSPOT_COMPANY_ID_FIELD_NAME = "HubSpot Company ID"
APPROVAL_MARKER = "confirm IFI"
MAX_JIRA_RESULTS = 5
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"
COMPANY_CONFIRMATION_GUIDANCE = "Reply with a HubSpot company link or numeric HubSpot Company ID before IFI can be written."
HUBSPOT_COMPANY_ID_RE = re.compile(
    r"(?:/company/|/record/0-2/)(\d+)(?:[/?#]|$)|^\s*(\d+)\s*$",
)
KER_RE = re.compile(r"\bKER-\d+\b", re.IGNORECASE)
BD_NOTE_COMPANY_RE = re.compile(
    r"^\s*(?P<company>.+?)\s+"
    r"(?P<verb>asked|asks|ask|requested|requests|request|mentioned|mentions|mention|wanted|wants|want|needs|need)\b",
    re.IGNORECASE,
)

mcp = FastMCP(
    "launchbot_ifi",
    instructions=(
        "Launchbot adapter for APQ/Slack feature-demand tracking. It resolves "
        "HubSpot companies, previews IFI create/update payloads, and mutates Jira "
        "only after the exact approval marker 'confirm IFI'. It never posts Slack "
        "messages or treats Jira Organizations as HubSpot truth."
    ),
)


class LaunchbotIfiError(RuntimeError):
    pass


def _scope(hubspot_company: str, feature_gap: str, slack_permalink: str) -> dict[str, Any]:
    return {
        "hubspot_company": hubspot_company.strip(),
        "feature_gap": _single_line(feature_gap, 160),
        "slack_permalink": slack_permalink.strip(),
        "project_key": _ifi_project_key(),
        "hubspot_company_id_field_id": _hubspot_company_id_field_id(),
        "approval_marker": APPROVAL_MARKER,
        "will_post_message": False,
        "requires_confirmation_for_mutation": True,
    }


def _blocked(message: str, source: str, scope: dict[str, Any], details: dict[str, Any] | None = None) -> dict[str, Any]:
    answer: dict[str, Any] = {"message": message}
    if details:
        answer.update(details)
    return {
        "answer": answer,
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
        "caveat": "Preview only; resolve ambiguity before writing IFI.",
    }


def _verified(answer: dict[str, Any], source: str, scope: dict[str, Any], caveat: str) -> dict[str, Any]:
    return {
        "answer": answer,
        "source": source,
        "scope": scope,
        "confidence": "verified",
        "caveat": caveat,
    }


def _safe_error(message: str) -> str:
    safe = str(message)
    for name in ("JIRA_API_TOKEN", "HUBSPOT_ACCESS_TOKEN", "HUBSPOT_PRIVATE_APP_TOKEN", "SLACK_BOT_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            safe = safe.replace(value, f"[REDACTED_{name}]")
    return safe[:500]


def _jira_base_url() -> str:
    return (os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_BASE_URL).strip() or DEFAULT_JIRA_BASE_URL).rstrip("/")


def _hubspot_portal_id() -> str:
    return os.environ.get("HUBSPOT_PORTAL_ID", DEFAULT_HUBSPOT_PORTAL_ID).strip() or DEFAULT_HUBSPOT_PORTAL_ID


def _ifi_project_key() -> str:
    return os.environ.get("JIRA_IFI_PROJECT_KEY", DEFAULT_IFI_PROJECT_KEY).strip() or DEFAULT_IFI_PROJECT_KEY


def _ifi_issue_type_id() -> str:
    return os.environ.get("JIRA_IFI_FEATURE_REQUEST_ISSUE_TYPE_ID", DEFAULT_IFI_ISSUE_TYPE_ID).strip() or DEFAULT_IFI_ISSUE_TYPE_ID


def _hubspot_company_id_field_id() -> str:
    return os.environ.get("JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_ID", DEFAULT_HUBSPOT_COMPANY_ID_FIELD_ID).strip() or DEFAULT_HUBSPOT_COMPANY_ID_FIELD_ID


def _hubspot_company_id_field_name() -> str:
    return os.environ.get("JIRA_IFI_HUBSPOT_COMPANY_ID_FIELD_NAME", DEFAULT_HUBSPOT_COMPANY_ID_FIELD_NAME).strip() or DEFAULT_HUBSPOT_COMPANY_ID_FIELD_NAME


def _jira_headers() -> dict[str, str]:
    email = os.environ.get("JIRA_EMAIL", "").strip()
    token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not email or not token:
        raise LaunchbotIfiError("Missing JIRA_EMAIL or JIRA_API_TOKEN.")
    encoded = base64.b64encode(f"{email}:{token}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def _hubspot_headers() -> dict[str, str]:
    token = (
        os.environ.get("HUBSPOT_ACCESS_TOKEN", "").strip()
        or os.environ.get("HUBSPOT_PRIVATE_APP_TOKEN", "").strip()
    )
    if not token:
        raise LaunchbotIfiError("Missing HUBSPOT_ACCESS_TOKEN or HUBSPOT_PRIVATE_APP_TOKEN.")
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def _request_json(method: str, url: str, headers: dict[str, str], body: dict[str, Any] | None = None) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=JIRA_TIMEOUT_SECONDS if "atlassian.net" in url else HUBSPOT_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotIfiError(_safe_error(f"{method} {url} failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotIfiError(_safe_error(f"{method} {url} failed: {reason}")) from error


def _jira_get(path: str) -> dict[str, Any]:
    return _request_json("GET", f"{_jira_base_url()}{path}", _jira_headers())


def _jira_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"{_jira_base_url()}{path}", _jira_headers(), body)


def _jira_put(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("PUT", f"{_jira_base_url()}{path}", _jira_headers(), body)


def _hubspot_get(path: str) -> dict[str, Any]:
    return _request_json("GET", f"https://api.hubapi.com{path}", _hubspot_headers())


def _hubspot_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    return _request_json("POST", f"https://api.hubapi.com{path}", _hubspot_headers(), body)


def _single_line(value: str, limit: int = 500) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip())
    return text[:limit]


def _parse_hubspot_company_id(value: str) -> str:
    match = HUBSPOT_COMPANY_ID_RE.search(value or "")
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def _company_url(company_id: str) -> str:
    return f"https://app.hubspot.com/contacts/{_hubspot_portal_id()}/company/{company_id}"


def _company_from_hubspot_payload(payload: dict[str, Any]) -> dict[str, str]:
    props = payload.get("properties") or {}
    company_id = str(payload.get("id") or props.get("hs_object_id") or "")
    return {
        "hubspotCompanyId": company_id,
        "name": str(props.get("name") or "Unnamed HubSpot company"),
        "domain": str(props.get("domain") or ""),
        "lifecycleStage": str(props.get("lifecyclestage") or ""),
        "hubspotUrl": _company_url(company_id) if company_id else "",
    }


def _company_search(query: str, limit: int = 5) -> list[dict[str, str]]:
    payload = _hubspot_post(
        "/crm/v3/objects/companies/search",
        {
            "query": query,
            "limit": limit,
            "properties": ["name", "domain", "lifecyclestage"],
        },
    )
    return [_company_from_hubspot_payload(item) for item in payload.get("results", []) if isinstance(item, dict)]


def _company_candidate_terms(query: str) -> list[str]:
    stop_words = {
        "company",
        "group",
        "holdings",
        "holding",
        "pte",
        "ltd",
        "limited",
        "staffany",
        "client",
        "customer",
        "prospect",
    }
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", query):
        normalized = token.lower()
        if normalized in stop_words:
            continue
        if normalized not in {term.lower() for term in terms}:
            terms.append(token)
    return terms[:3]


def _resolve_hubspot_company(value: str) -> tuple[str, dict[str, Any] | list[dict[str, str]]]:
    company_id = _parse_hubspot_company_id(value)
    if company_id:
        payload = _hubspot_get(
            f"/crm/v3/objects/companies/{urllib.parse.quote(company_id)}?properties=name,domain,lifecyclestage"
        )
        return "verified", _company_from_hubspot_payload(payload)

    query = value.strip()
    if not query:
        return "blocked", {"message": "hubspot_company is required."}
    matches = _company_search(query)
    if len(matches) == 1:
        return "verified", matches[0]
    if not matches:
        fallback_matches: list[dict[str, str]] = []
        seen_ids: set[str] = set()
        for term in _company_candidate_terms(query):
            for match in _company_search(term):
                company_id_value = match.get("hubspotCompanyId") or ""
                if company_id_value and company_id_value not in seen_ids:
                    seen_ids.add(company_id_value)
                    fallback_matches.append(match)
        if fallback_matches:
            return "needs-check", fallback_matches[:5]
    return "needs-check", matches


def _bd_note_extraction(bd_note: str, hubspot_company: str) -> dict[str, str]:
    text = _single_line(bd_note, 1000)
    company_hint = _single_line(hubspot_company, 180)
    match = BD_NOTE_COMPANY_RE.search(text)
    if match and not company_hint:
        company_hint = _single_line(match.group("company"), 180)

    lower = text.lower()
    if "citibank" in lower and "bank file" in lower:
        feature_gap = "Citibank bank file export"
    else:
        feature_gap = ""
        for pattern in [
            r"(?:generate|support|build|do|create)\s+(?P<feature>.+?)(?:[.?!]|$)",
            r"(?:asked|requested|wanted|needs?)\s+(?:whether|if|for)?\s*(?P<feature>.+?)(?:[.?!]|$)",
        ]:
            feature_match = re.search(pattern, text, re.IGNORECASE)
            if feature_match:
                feature_gap = _single_line(feature_match.group("feature"), 180)
                break
        if not feature_gap:
            feature_gap = _single_line(text, 180)

    return {
        "companyHint": company_hint,
        "featureGap": feature_gap,
        "originalQuestion": text,
    }


def _attach_extraction(result: dict[str, Any], extraction: dict[str, str]) -> dict[str, Any]:
    answer = result.setdefault("answer", {})
    if isinstance(answer, dict):
        answer["bdNoteExtraction"] = extraction
        if result.get("confidence") == "needs-check":
            answer.setdefault("nextAction", COMPANY_CONFIRMATION_GUIDANCE)
    return result


def _jql_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace('"', '\\"')


def _feature_keyword(feature_gap: str) -> str:
    stop_words = {
        "and",
        "the",
        "for",
        "with",
        "file",
        "export",
        "native",
        "support",
        "request",
        "feature",
    }
    for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{2,}", feature_gap.lower()):
        if token not in stop_words:
            return token
    return ""


def _build_dedupe_jql(hubspot_company_id: str, feature_gap: str) -> str:
    field_name = _hubspot_company_id_field_name()
    clauses = [
        f'project = {_ifi_project_key()}',
        f'"{_jql_escape(field_name)}" ~ "{_jql_escape(hubspot_company_id)}"',
    ]
    keyword = _feature_keyword(feature_gap)
    if keyword:
        clauses.append(f'text ~ "{_jql_escape(keyword)}"')
    return f"{' AND '.join(clauses)} ORDER BY updated DESC"


def _tracking_block(
    *,
    company: dict[str, str],
    requester: str,
    slack_permalink: str,
    feature_gap: str,
    original_question: str,
    apq_classification: str,
    linked_ker_key: str,
) -> str:
    ker_key = linked_ker_key.strip().upper()
    if ker_key and not KER_RE.fullmatch(ker_key):
        ker_key = ""
    detailed_problem = str(original_question or "").strip() or "Not provided"
    return "\n".join(
        [
            "Customer context",
            f"- HubSpot Company ID: {company['hubspotCompanyId']}",
            f"- HubSpot Company URL: {company['hubspotUrl']}",
            f"- Requester: {_single_line(requester, 160) or 'Not provided'}",
            f"- Source Slack thread: {slack_permalink.strip() or 'Not provided'}",
            "",
            "Product request summary",
            f"- Feature gap: {_single_line(feature_gap, 180)}",
            f"- APQ classification: {_single_line(apq_classification, 160) or 'needs product review'}",
            f"- Linked KER: {ker_key or 'none yet'}",
            "",
            "Detailed request / problem",
            detailed_problem,
        ]
    )


def _adf_from_text(text: str) -> dict[str, Any]:
    content = []
    for line in text.splitlines():
        paragraph: dict[str, Any] = {"type": "paragraph"}
        if line:
            paragraph["content"] = [{"type": "text", "text": line}]
        content.append(paragraph)
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph"}]}


def _adf_to_text(node: Any) -> str:
    lines: list[str] = []

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("type") == "text":
                lines.append(str(value.get("text") or ""))
            elif value.get("type") == "paragraph" and lines and lines[-1] != "\n":
                lines.append("\n")
            for child in value.get("content") or []:
                visit(child)
            if value.get("type") == "paragraph":
                lines.append("\n")
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(node)
    return re.sub(r"\n{3,}", "\n\n", "".join(lines)).strip()


def _issue_candidate(issue: dict[str, Any]) -> dict[str, Any]:
    fields = issue.get("fields") or {}
    linked_keys = [
        linked
        for link in fields.get("issuelinks") or []
        for linked in [
            ((link.get("outwardIssue") or {}).get("key")),
            ((link.get("inwardIssue") or {}).get("key")),
        ]
        if linked
    ]
    return {
        "issueKey": issue.get("key") or "",
        "summary": fields.get("summary") or issue.get("key") or "",
        "status": (fields.get("status") or {}).get("name") or "Not set",
        "issueType": (fields.get("issuetype") or {}).get("name") or "Not set",
        "updated": fields.get("updated") or "",
        "hubspotCompanyId": fields.get(_hubspot_company_id_field_id()) or "",
        "linkedKeys": linked_keys,
        "url": f"{_jira_base_url()}/browse/{issue.get('key')}",
    }


def _search_existing_ifi(hubspot_company_id: str, feature_gap: str) -> tuple[str, list[dict[str, Any]]]:
    jql = _build_dedupe_jql(hubspot_company_id, feature_gap)
    payload = _jira_post(
        "/rest/api/3/search/jql",
        {
            "jql": jql,
            "maxResults": MAX_JIRA_RESULTS,
            "fields": [
                "summary",
                "status",
                "issuetype",
                "updated",
                "issuelinks",
                _hubspot_company_id_field_id(),
            ],
        },
    )
    return jql, [_issue_candidate(issue) for issue in payload.get("issues", []) if isinstance(issue, dict)]


def _summary(feature_gap: str, company: dict[str, str]) -> str:
    return _single_line(f"{_single_line(feature_gap, 150)} — {company['name']}", 240)


def _build_preview(
    *,
    hubspot_company: str,
    feature_gap: str,
    original_question: str,
    requester: str,
    slack_permalink: str,
    apq_classification: str,
    linked_ker_key: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    scope = _scope(hubspot_company, feature_gap, slack_permalink)
    if not feature_gap.strip():
        return scope, _blocked("feature_gap is required.", "Launchbot IFI MCP", scope)
    if not original_question.strip():
        return scope, _blocked("original_question is required.", "Launchbot IFI MCP", scope)

    try:
        resolution_status, resolution = _resolve_hubspot_company(hubspot_company)
    except LaunchbotIfiError as error:
        return scope, _blocked(str(error), "HubSpot company API", scope)

    if resolution_status == "blocked":
        return scope, _blocked(str(resolution.get("message") or "HubSpot company could not be resolved."), "HubSpot company API", scope)
    if resolution_status == "needs-check":
        return scope, _needs_check(
            "HubSpot company lookup is ambiguous or empty.",
            "HubSpot company search API",
            scope,
            {"hubspotCandidates": resolution, "nextAction": COMPANY_CONFIRMATION_GUIDANCE},
        )

    company = resolution
    try:
        dedupe_jql, existing_issues = _search_existing_ifi(company["hubspotCompanyId"], feature_gap)
    except LaunchbotIfiError as error:
        return scope, _blocked(str(error), "Jira IFI search API", scope)

    description = _tracking_block(
        company=company,
        requester=requester,
        slack_permalink=slack_permalink,
        feature_gap=feature_gap,
        original_question=original_question,
        apq_classification=apq_classification,
        linked_ker_key=linked_ker_key,
    )
    operation = "update" if existing_issues else "create"
    issue = existing_issues[0] if existing_issues else None
    answer = {
        "operation": operation,
        "hubspotCompany": company,
        "dedupeJql": dedupe_jql,
        "existingIssue": issue,
        "jiraIssuePayload": {
            "projectKey": _ifi_project_key(),
            "issueTypeId": _ifi_issue_type_id(),
            "summary": _summary(feature_gap, company),
            "hubspotCompanyIdFieldId": _hubspot_company_id_field_id(),
            "hubspotCompanyId": company["hubspotCompanyId"],
            "descriptionPreview": description,
            "linkedKerKey": linked_ker_key.strip().upper() if KER_RE.fullmatch(linked_ker_key.strip().upper()) else "",
        },
        "slackReplyPreview": _slack_reply(issue["issueKey"], issue["url"], company) if issue else "",
        "willMutateJira": False,
        "willPostMessage": False,
    }
    return scope, _verified(
        answer,
        "HubSpot company API + Jira IFI search API",
        scope,
        "Preview only. Call create_or_update_ifi_feature_request_tracking with approval_marker='confirm IFI' to write Jira.",
    )


def _slack_reply(issue_key: str, issue_url: str, company: dict[str, str]) -> str:
    return (
        "Launchbot automation: IFI tracked "
        f"<{issue_url}|{issue_key}> for {company['name']} "
        f"(HubSpot Company ID {company['hubspotCompanyId']})."
    )


def _link_ker_if_needed(issue_key: str, linked_ker_key: str) -> str:
    key = linked_ker_key.strip().upper()
    if not key:
        return ""
    if not KER_RE.fullmatch(key):
        return "linked_ker_key ignored because it does not look like KER-123."
    issue = _jira_get(f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}?fields=issuelinks")
    existing = {
        linked
        for link in (issue.get("fields") or {}).get("issuelinks") or []
        for linked in [
            ((link.get("outwardIssue") or {}).get("key")),
            ((link.get("inwardIssue") or {}).get("key")),
        ]
        if linked
    }
    if key in existing:
        return ""
    _jira_post(
        "/rest/api/3/issueLink",
        {
            "type": {"name": "Relates"},
            "inwardIssue": {"key": issue_key},
            "outwardIssue": {"key": key},
        },
    )
    return ""


def _mutate_verified_preview(scope: dict[str, Any], preview: dict[str, Any]) -> dict[str, Any]:
    answer = preview["answer"]
    payload = answer["jiraIssuePayload"]
    company = answer["hubspotCompany"]
    field_id = _hubspot_company_id_field_id()
    description = payload["descriptionPreview"]
    warnings: list[str] = []

    try:
        if answer["operation"] == "update" and answer.get("existingIssue"):
            issue_key = answer["existingIssue"]["issueKey"]
            issue = _jira_get(f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}?fields=description")
            existing_description = _adf_to_text((issue.get("fields") or {}).get("description"))
            if existing_description and description not in existing_description:
                next_description = f"{existing_description}\n\n{description}"
            else:
                next_description = existing_description or description
            _jira_put(
                f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}",
                {"fields": {field_id: company["hubspotCompanyId"], "description": _adf_from_text(next_description)}},
            )
            operation = "updated"
        else:
            created = _jira_post(
                "/rest/api/3/issue",
                {
                    "fields": {
                        "project": {"key": _ifi_project_key()},
                        "issuetype": {"id": _ifi_issue_type_id()},
                        "summary": payload["summary"],
                        "description": _adf_from_text(description),
                        field_id: company["hubspotCompanyId"],
                        "labels": ["apq-tracked", "hubspot-linked"],
                    }
                },
            )
            issue_key = created.get("key") or ""
            operation = "created"
        ker_warning = _link_ker_if_needed(issue_key, payload.get("linkedKerKey", ""))
        if ker_warning:
            warnings.append(ker_warning)
    except LaunchbotIfiError as error:
        return _blocked(str(error), "Jira IFI mutation API", scope, {"preview": preview["answer"]})

    issue_url = f"{_jira_base_url()}/browse/{issue_key}"
    return _verified(
        {
            "operation": operation,
            "issueKey": issue_key,
            "issueUrl": issue_url,
            "hubspotCompany": company,
            "warnings": warnings,
            "slackReply": _slack_reply(issue_key, issue_url, company),
            "willMutateJira": True,
            "willPostMessage": False,
        },
        "HubSpot company API + Jira IFI mutation API",
        scope,
        "Jira was mutated only after exact approval marker; Launchbot MCP did not post to Slack.",
    )


@mcp.tool()
def preview_ifi_feature_request_tracking(
    hubspot_company: str = "",
    feature_gap: str = "",
    original_question: str = "",
    requester: str = "",
    slack_permalink: str = "",
    apq_classification: str = "Capability gap / needs product review",
    linked_ker_key: str = "",
) -> dict[str, Any]:
    """Preview APQ/Slack feature-demand tracking into IFI. No Jira mutation."""

    _scope_value, result = _build_preview(
        hubspot_company=hubspot_company,
        feature_gap=feature_gap,
        original_question=original_question,
        requester=requester,
        slack_permalink=slack_permalink,
        apq_classification=apq_classification,
        linked_ker_key=linked_ker_key,
    )
    return result


@mcp.tool()
def preview_ifi_feature_request_from_bd_note(
    bd_note: str = "",
    hubspot_company: str = "",
    requester: str = "",
    slack_permalink: str = "",
    apq_classification: str = "BD notes feature request / needs product review",
    linked_ker_key: str = "",
) -> dict[str, Any]:
    """Preview BD-note feature-demand tracking into IFI. No Jira mutation."""

    extraction = _bd_note_extraction(bd_note, hubspot_company)
    if not bd_note.strip():
        scope = _scope(hubspot_company, "", slack_permalink)
        return _attach_extraction(_blocked("bd_note is required.", "Launchbot IFI MCP", scope), extraction)
    if not extraction["companyHint"]:
        scope = _scope(hubspot_company, extraction["featureGap"], slack_permalink)
        return _attach_extraction(
            _needs_check(
                "BD note did not include a usable company hint.",
                "Launchbot IFI MCP",
                scope,
                {"nextAction": COMPANY_CONFIRMATION_GUIDANCE},
            ),
            extraction,
        )

    _scope_value, result = _build_preview(
        hubspot_company=extraction["companyHint"],
        feature_gap=extraction["featureGap"],
        original_question=extraction["originalQuestion"],
        requester=requester,
        slack_permalink=slack_permalink,
        apq_classification=apq_classification,
        linked_ker_key=linked_ker_key,
    )
    return _attach_extraction(result, extraction)


@mcp.tool()
def create_or_update_ifi_feature_request_tracking(
    hubspot_company: str = "",
    feature_gap: str = "",
    original_question: str = "",
    requester: str = "",
    slack_permalink: str = "",
    apq_classification: str = "Capability gap / needs product review",
    linked_ker_key: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Create/update IFI tracking after exact approval marker 'confirm IFI'."""

    scope, preview = _build_preview(
        hubspot_company=hubspot_company,
        feature_gap=feature_gap,
        original_question=original_question,
        requester=requester,
        slack_permalink=slack_permalink,
        apq_classification=apq_classification,
        linked_ker_key=linked_ker_key,
    )
    if preview.get("confidence") != "verified":
        return preview
    if approval_marker.strip() != APPROVAL_MARKER:
        return _blocked(
            "approval_marker must be exactly 'confirm IFI' before Jira mutation.",
            "Launchbot IFI MCP",
            scope,
            {"preview": preview["answer"]},
        )

    return _mutate_verified_preview(scope, preview)


@mcp.tool()
def create_or_update_ifi_feature_request_from_bd_note(
    bd_note: str = "",
    hubspot_company: str = "",
    requester: str = "",
    slack_permalink: str = "",
    apq_classification: str = "BD notes feature request / needs product review",
    linked_ker_key: str = "",
    approval_marker: str = "",
) -> dict[str, Any]:
    """Create/update IFI tracking from a BD note after exact approval marker 'confirm IFI'."""

    extraction = _bd_note_extraction(bd_note, hubspot_company)
    preview = preview_ifi_feature_request_from_bd_note(
        bd_note=bd_note,
        hubspot_company=hubspot_company,
        requester=requester,
        slack_permalink=slack_permalink,
        apq_classification=apq_classification,
        linked_ker_key=linked_ker_key,
    )
    scope = _scope(extraction["companyHint"], extraction["featureGap"], slack_permalink)
    if preview.get("confidence") != "verified":
        return preview
    if approval_marker.strip() != APPROVAL_MARKER:
        return _blocked(
            "approval_marker must be exactly 'confirm IFI' before Jira mutation.",
            "Launchbot IFI MCP",
            scope,
            {"preview": preview["answer"]},
        )
    result = _mutate_verified_preview(scope, preview)
    return _attach_extraction(result, extraction)


if __name__ == "__main__":
    mcp.run("stdio")
