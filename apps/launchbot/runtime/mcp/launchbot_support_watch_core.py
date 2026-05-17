#!/usr/bin/env python3
"""Read-only weekly support-watch analysis for Launchbot."""

from __future__ import annotations

import base64
import json
import os
import re
import shutil
import socket
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from profile_env import load_profile_env


load_profile_env()

SLACK_API_BASE_URL = "https://slack.com/api/"
DEFAULT_JIRA_BASE_URL = "https://staffany.atlassian.net"
USER_AGENT = "StaffAny-Launchbot/1.0 (+https://staffany.com)"
DEFAULT_LOOKBACK_DAYS = 7
DEFAULT_SUPPORT_WATCH_SOURCE = "bigquery"
DEFAULT_BIGQUERY_PROJECT = "staffany-warehouse"
DEFAULT_INTERCOM_BIGQUERY_DATASET = "intercom"
DEFAULT_ANALYTICS_BIGQUERY_DATASET = "analytics"
DEFAULT_WHATSAPP_BIGQUERY_VIEW = "gsheets.cs_tickets_logs_all_view"
DEFAULT_INCLUDE_WHATSAPP = True
DEFAULT_MAX_SUPPORT_ITEMS = 100
DEFAULT_MAX_TICKETS = DEFAULT_MAX_SUPPORT_ITEMS
SUPPORT_PROBLEM_PATTERN = r"\b(cannot|unable|failed|failure|error|blocked|missing|wrong|incorrect|stuck|down|outage|bug|broken|not working|doesn.?t work|trouble|issue|crash|timeout)\b"
SUPPORT_PRODUCT_PATTERN = r"\b(payroll|clock|timesheet|attendance|leave|overtime|schedule|shift|login|mobile|permission|cpf|bank file|payslip|salary|statutory|onboarding)\b"
SUPPORT_NOISE_PATTERN = r"\b(in the help center|article inserter|troubleshooting:|how to|learn how to)\b"
MAX_SAFE_TICKETS_PER_FINDING = 5
MAX_FINDINGS = 8
DEFAULT_EDT_JQL = 'project = PCO AND "PS Team" = "Eng Duty" AND statusCategory != Done ORDER BY updated DESC'
OUTPUT_CHANNEL_NAME = "all-bugs-production"
STATE_STATUS_NEW = "new"
STATE_STATUS_DEDUPED = "deduped"


class LaunchbotSupportWatchError(RuntimeError):
    pass


STOP_WORDS = {
    "able",
    "about",
    "after",
    "again",
    "also",
    "and",
    "any",
    "are",
    "but",
    "can",
    "cannot",
    "cant",
    "customer",
    "customers",
    "did",
    "does",
    "done",
    "email",
    "error",
    "for",
    "from",
    "has",
    "have",
    "help",
    "into",
    "issue",
    "its",
    "not",
    "now",
    "our",
    "please",
    "phone",
    "production",
    "support",
    "that",
    "the",
    "their",
    "them",
    "there",
    "this",
    "ticket",
    "unable",
    "user",
    "users",
    "when",
    "with",
    "working",
}

PRODUCT_HINTS = {
    "PayrollAny": ("payroll", "payslip", "cpf", "bank file", "disbursement", "salary", "pay run", "statutory"),
    "EngageAny": ("attendance", "timesheet", "clock", "shift", "schedule", "leave", "overtime"),
    "HRAny": ("onboarding", "document", "employee profile", "career", "contract", "form"),
    "StaffAny": ("login", "mobile", "permission", "settings", "notification", "account"),
}

HIGH_SEVERITY_RE = re.compile(
    r"(?i)\b("
    r"outage|down|blocked|cannot\s+(?:run|submit|login|pay|clock)|unable\s+(?:to\s+)?(?:run|submit|login|pay|clock)|"
    r"payroll\s+(?:blocked|failed|cannot|unable)|production\s+(?:bug|issue|down)|data\s+(?:loss|missing|wrong)"
    r")\b"
)
ERROR_SIGNATURE_RE = re.compile(
    r"(?i)\b(?:error|failed|failure|cannot|unable|stuck|missing|wrong|incorrect|blocked)\b[:\s-]*([^.;\n]{0,90})"
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str, fallback: datetime) -> datetime:
    raw = (value or "").strip()
    if not raw:
        return fallback
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError as error:
        raise LaunchbotSupportWatchError(f"Invalid ISO timestamp: {raw}") from error


def unix_timestamp(dt: datetime) -> int:
    return int(dt.astimezone(timezone.utc).timestamp())


def safe_text(value: Any, limit: int = 500) -> str:
    text = str(value or "").replace("\n", " ").strip()
    text = re.sub(r"<@[^>]+>", "<@user>", text)
    text = re.sub(r"<#[^>]+>", "<#channel>", text)
    text = re.sub(r"<(https?://[^>|]+)(?:\|[^>]+)?>", r"\1", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", "[email]", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)", "[phone]", text)
    text = re.sub(r"\s+", " ", text)
    return text[:limit]


def safe_error(message: str) -> str:
    safe = str(message)
    for name in ("SLACK_BOT_TOKEN", "JIRA_API_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            safe = safe.replace(value, f"[REDACTED_{name}]")
    return safe[:400]


def token(primary: str, fallbacks: tuple[str, ...] = ()) -> str:
    for name in (primary, *fallbacks):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    names = ", ".join((primary, *fallbacks))
    raise LaunchbotSupportWatchError(f"Missing token env: {names}.")


def scope(window_start: datetime, window_end: datetime, max_tickets: int) -> dict[str, Any]:
    return {
        "window_start": isoformat(window_start),
        "window_end": isoformat(window_end),
        "max_tickets": max_tickets,
        "source": os.environ.get("LAUNCHBOT_SUPPORT_WATCH_SOURCE", DEFAULT_SUPPORT_WATCH_SOURCE) or DEFAULT_SUPPORT_WATCH_SOURCE,
        "intercom_project": bigquery_project(),
        "intercom_dataset": intercom_bigquery_dataset(),
        "include_whatsapp": include_whatsapp_source(),
        "whatsapp_view": whatsapp_bigquery_view(),
        "output_channel_name": os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_NAME", OUTPUT_CHANNEL_NAME) or OUTPUT_CHANNEL_NAME,
        "output_channel_id": os.environ.get("LAUNCHBOT_SUPPORT_WATCH_OUTPUT_CHANNEL_ID", ""),
        "dedupe_channel_ids_env": "LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS",
        "edt_jql_env": "LAUNCHBOT_SUPPORT_WATCH_EDT_JQL",
        "will_post_message": False,
        "will_create_ticket": False,
        "will_tag_engineer": False,
        "raw_transcript_persisted": False,
    }


def blocked(message: str, source: str, scope_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "answer": message,
        "source": source,
        "scope": scope_data,
        "confidence": "blocked",
        "caveat": "No Slack post, ticket creation, assignment, or engineer tag was performed.",
    }


def bigquery_project() -> str:
    return (
        os.environ.get("LAUNCHBOT_SUPPORT_WATCH_INTERCOM_PROJECT", "").strip()
        or os.environ.get("BIGQUERY_PROJECT_ID", "").strip()
        or DEFAULT_BIGQUERY_PROJECT
    )


def intercom_bigquery_dataset() -> str:
    return (
        os.environ.get("LAUNCHBOT_SUPPORT_WATCH_INTERCOM_DATASET", "").strip()
        or os.environ.get("INTERCOM_BIGQUERY_DATASET", "").strip()
        or DEFAULT_INTERCOM_BIGQUERY_DATASET
    )


def analytics_bigquery_dataset() -> str:
    return (
        os.environ.get("LAUNCHBOT_SUPPORT_WATCH_ANALYTICS_DATASET", "").strip()
        or os.environ.get("ANALYTICS_BIGQUERY_DATASET", "").strip()
        or DEFAULT_ANALYTICS_BIGQUERY_DATASET
    )


def whatsapp_bigquery_view() -> str:
    return os.environ.get("LAUNCHBOT_SUPPORT_WATCH_WHATSAPP_VIEW", "").strip() or DEFAULT_WHATSAPP_BIGQUERY_VIEW


def include_whatsapp_source() -> bool:
    raw = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_INCLUDE_WHATSAPP", "").strip().lower()
    if not raw:
        return DEFAULT_INCLUDE_WHATSAPP
    return raw not in {"0", "false", "no", "off"}


def bigquery_table_ref(name: str, default_project: str = "") -> str:
    raw = (name or "").strip().strip("`")
    if not raw:
        raise LaunchbotSupportWatchError("Missing BigQuery table reference.")
    parts = raw.split(".")
    if len(parts) == 1:
        parts = [default_project or bigquery_project(), raw]
    elif len(parts) == 2:
        parts = [default_project or bigquery_project(), *parts]
    elif len(parts) != 3:
        raise LaunchbotSupportWatchError(f"Invalid BigQuery table reference: {raw}")
    return f"`{'.'.join(parts)}`"


def run_bigquery_query(query: str, params: dict[str, tuple[str, str]], *, project: str = "") -> list[dict[str, Any]]:
    bq_binary = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_BQ_BIN", "").strip() or "bq"
    bq_path = shutil.which(bq_binary)
    if not bq_path:
        raise LaunchbotSupportWatchError("Missing BigQuery CLI: bq.")
    command = [bq_path, "--format=json"]
    selected_project = project or bigquery_project()
    if selected_project:
        command.extend(["--project_id", selected_project])
    location = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_BIGQUERY_LOCATION", "").strip() or os.environ.get("BIGQUERY_LOCATION", "").strip()
    if location:
        command.extend(["--location", location])
    command.extend(["query", "--use_legacy_sql=false"])
    for name, (param_type, value) in params.items():
        command.extend(["--parameter", f"{name}:{param_type}:{value}"])
    command.append(query)
    try:
        result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise LaunchbotSupportWatchError(safe_error(f"BigQuery query failed: {error}")) from error
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise LaunchbotSupportWatchError(safe_error(f"BigQuery query failed: {detail}"))
    stdout = result.stdout.strip()
    if not stdout:
        return []
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise LaunchbotSupportWatchError(safe_error(f"BigQuery returned invalid JSON: {error}")) from error
    if not isinstance(rows, list):
        raise LaunchbotSupportWatchError("BigQuery returned an unexpected response shape.")
    return [row for row in rows if isinstance(row, dict)]


def jira_headers() -> dict[str, str]:
    email = os.environ.get("JIRA_EMAIL", "").strip()
    api_token = os.environ.get("JIRA_API_TOKEN", "").strip()
    if not email or not api_token:
        raise LaunchbotSupportWatchError("Missing JIRA_EMAIL or JIRA_API_TOKEN.")
    encoded = base64.b64encode(f"{email}:{api_token}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "User-Agent": USER_AGENT,
    }


def jira_base_url() -> str:
    return (os.environ.get("JIRA_BASE_URL", DEFAULT_JIRA_BASE_URL).strip() or DEFAULT_JIRA_BASE_URL).rstrip("/")


def jira_post(path: str, body: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        f"{jira_base_url()}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers=jira_headers(),
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotSupportWatchError(safe_error(f"Jira API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotSupportWatchError(safe_error(f"Jira API request failed: {reason}")) from error


def slack_api(method: str, params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = urllib.parse.urljoin(SLACK_API_BASE_URL, method)
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token('SLACK_BOT_TOKEN')}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise LaunchbotSupportWatchError(safe_error(f"Slack API failed: {error.code} {detail}")) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise LaunchbotSupportWatchError(safe_error(f"Slack API request failed: {reason}")) from error
    if not payload.get("ok"):
        raise LaunchbotSupportWatchError(safe_error(f"Slack API returned error: {payload.get('error') or 'unknown_error'}"))
    return payload


def intercom_conversation_url(conversation_id: str) -> str:
    app_id = os.environ.get("LAUNCHBOT_INTERCOM_APP_ID", "").strip() or os.environ.get("LAUNCH_STEP3_INTERCOM_APP_ID", "").strip()
    if app_id and conversation_id:
        return f"https://app.intercom.com/a/apps/{app_id}/inbox/inbox/conversation/{urllib.parse.quote(conversation_id)}"
    return f"https://app.intercom.com/a/inbox/search?query={urllib.parse.quote(conversation_id)}" if conversation_id else ""


def jira_issue_url(issue_key: str) -> str:
    key = (issue_key or "").strip()
    if re.fullmatch(r"[A-Z][A-Z0-9]+-\d+", key):
        return f"{DEFAULT_JIRA_BASE_URL}/browse/{urllib.parse.quote(key)}"
    return ""


def build_intercom_conversations_query() -> str:
    intercom_dataset = intercom_bigquery_dataset()
    project = bigquery_project()
    conversations_table = bigquery_table_ref(f"{intercom_dataset}.conversations", project)
    parts_table = bigquery_table_ref(f"{intercom_dataset}.conversation_parts", project)
    companies_table = bigquery_table_ref(f"{intercom_dataset}.companies", project)
    users_table = bigquery_table_ref(f"{intercom_dataset}.users", project)
    dim_org_company = bigquery_table_ref(f"{analytics_bigquery_dataset()}.dim_org_company", project)
    return f"""
      WITH mapped_orgs AS (
        SELECT DISTINCT
          CAST(SAFE_CAST(company_id AS INT64) AS STRING) AS hubspot_company_id,
          company_name,
          CAST(organisation_id AS STRING) AS organisation_id,
          organisation_name
        FROM {dim_org_company}
        WHERE organisation_id IS NOT NULL
      ),
      latest_intercom_companies AS (
        SELECT
          id AS intercom_company_id,
          CAST(company_id AS STRING) AS organisation_id,
          name AS intercom_company_name
        FROM {companies_table}
        WHERE _PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 30 DAY)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY id
          ORDER BY updated_at DESC NULLS LAST, _PARTITIONTIME DESC
        ) = 1
      ),
      mapped_intercom_companies AS (
        SELECT DISTINCT
          mapped_orgs.hubspot_company_id,
          mapped_orgs.company_name,
          mapped_orgs.organisation_id,
          mapped_orgs.organisation_name,
          latest_intercom_companies.intercom_company_id,
          latest_intercom_companies.intercom_company_name
        FROM mapped_orgs
        JOIN latest_intercom_companies USING (organisation_id)
      ),
      latest_user_records AS (
        SELECT
          id AS intercom_user_id,
          user_id AS intercom_user_external_id,
          email AS intercom_user_email,
          name AS intercom_user_name,
          companies
        FROM {users_table}
        WHERE _PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 30 DAY)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY id
          ORDER BY updated_at DESC NULLS LAST, _PARTITIONTIME DESC
        ) = 1
      ),
      latest_user_companies AS (
        SELECT
          latest_user_records.*,
          TRIM(intercom_company_id) AS intercom_company_id
        FROM latest_user_records,
        UNNEST(SPLIT(IFNULL(companies, ''), ',')) AS intercom_company_id
        WHERE TRIM(intercom_company_id) != ''
      ),
      mapped_users AS (
        SELECT DISTINCT
          mapped_intercom_companies.*,
          latest_user_companies.intercom_user_id,
          latest_user_companies.intercom_user_external_id,
          latest_user_companies.intercom_user_email,
          latest_user_companies.intercom_user_name
        FROM latest_user_companies
        JOIN mapped_intercom_companies USING (intercom_company_id)
      ),
      latest_conversations AS (
        SELECT
          mapped_users.hubspot_company_id,
          mapped_users.company_name,
          mapped_users.organisation_id,
          mapped_users.organisation_name,
          mapped_users.intercom_company_id,
          mapped_users.intercom_company_name,
          mapped_users.intercom_user_id,
          mapped_users.intercom_user_external_id,
          mapped_users.intercom_user_email,
          mapped_users.intercom_user_name,
          conversations.id AS conversation_id,
          conversations.message_subject,
          conversations.message_body,
          conversations.tags,
          conversations.open AS is_open,
          SAFE_CAST(conversations.created_at AS TIMESTAMP) AS conversation_created_at,
          SAFE_CAST(conversations.updated_at AS TIMESTAMP) AS conversation_updated_at
        FROM {conversations_table} AS conversations
        LEFT JOIN mapped_users
          ON conversations.user_id = mapped_users.intercom_user_id
        WHERE conversations._PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 2 DAY)
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY conversations.id
          ORDER BY conversations.updated_at DESC NULLS LAST, conversations._PARTITIONTIME DESC
        ) = 1
      ),
      conversation_rows AS (
        SELECT
          'intercom_conversation' AS source_type,
          conversation_id AS id,
          conversation_id AS ticket_id,
          CAST(NULL AS STRING) AS part_id,
          message_subject AS title,
          message_body AS body,
          tags,
          IF(is_open, 'open', 'closed') AS state,
          is_open AS open,
          CAST(NULL AS STRING) AS team_assignee_id,
          CAST(NULL AS STRING) AS admin_assignee_id,
          conversation_created_at AS created_at,
          conversation_updated_at AS updated_at,
          conversation_id,
          hubspot_company_id,
          company_name,
          organisation_id,
          organisation_name,
          intercom_company_id,
          intercom_company_name,
          intercom_user_id,
          intercom_user_external_id,
          intercom_user_email,
          intercom_user_name
        FROM latest_conversations
        WHERE (
          conversation_created_at >= @windowStart AND conversation_created_at < @windowEnd
        ) OR (
          conversation_updated_at >= @windowStart AND conversation_updated_at < @windowEnd
        )
      ),
      part_rows AS (
        SELECT
          'intercom_conversation_part' AS source_type,
          CONCAT(latest_conversations.conversation_id, ':', parts.id) AS id,
          latest_conversations.conversation_id AS ticket_id,
          parts.id AS part_id,
          latest_conversations.message_subject AS title,
          parts.body AS body,
          latest_conversations.tags,
          CONCAT(IFNULL(parts.author_type, ''), ':', IFNULL(parts.part_type, '')) AS state,
          latest_conversations.is_open AS open,
          CAST(NULL AS STRING) AS team_assignee_id,
          CAST(NULL AS STRING) AS admin_assignee_id,
          SAFE_CAST(parts.created_at AS TIMESTAMP) AS created_at,
          SAFE_CAST(parts.updated_at AS TIMESTAMP) AS updated_at,
          latest_conversations.conversation_id,
          latest_conversations.hubspot_company_id,
          latest_conversations.company_name,
          latest_conversations.organisation_id,
          latest_conversations.organisation_name,
          latest_conversations.intercom_company_id,
          latest_conversations.intercom_company_name,
          latest_conversations.intercom_user_id,
          latest_conversations.intercom_user_external_id,
          latest_conversations.intercom_user_email,
          latest_conversations.intercom_user_name
        FROM {parts_table} AS parts
        JOIN latest_conversations
          ON parts.conversation_id = latest_conversations.conversation_id
        WHERE parts._PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 2 DAY)
          AND LOWER(IFNULL(parts.author_type, '')) IN ('user', 'lead', 'contact')
          AND (
            SAFE_CAST(parts.created_at AS TIMESTAMP) >= @windowStart AND SAFE_CAST(parts.created_at AS TIMESTAMP) < @windowEnd
          )
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY parts.id
          ORDER BY parts.updated_at DESC NULLS LAST, parts._PARTITIONTIME DESC
        ) = 1
      ),
      all_rows AS (
        SELECT * FROM conversation_rows
        UNION ALL
        SELECT * FROM part_rows
      ),
      scored_rows AS (
        SELECT
          *,
          LOWER(CONCAT(
            IFNULL(CAST(title AS STRING), ''),
            ' ',
            IFNULL(CAST(body AS STRING), ''),
            ' ',
            IFNULL(CAST(tags AS STRING), ''),
            ' ',
            IFNULL(CAST(company_name AS STRING), ''),
            ' ',
            IFNULL(CAST(organisation_name AS STRING), '')
          )) AS candidate_text
        FROM all_rows
      ),
      candidate_rows AS (
        SELECT
          *,
          IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}'), 1, 0) AS problem_score,
          IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_NOISE_PATTERN}'), 1, 0) AS noise_score,
          (
            IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}'), 10, 0)
            + IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PRODUCT_PATTERN}'), 3, 0)
            + IF(REGEXP_CONTAINS(candidate_text, r'\\b(blocked|down|outage|cannot|unable|failed)\\b'), 5, 0)
          ) AS candidate_score,
          CASE
            WHEN REGEXP_CONTAINS(candidate_text, r'\\b(blocked|down|outage|cannot|unable|failed)\\b') THEN 'high_severity_problem_keyword'
            WHEN REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}') THEN 'problem_keyword'
            ELSE 'not_candidate'
          END AS candidate_reason
        FROM scored_rows
      )
      SELECT * EXCEPT(candidate_text, problem_score, noise_score)
      FROM candidate_rows
      WHERE problem_score > 0
        AND noise_score = 0
      ORDER BY candidate_score DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
      LIMIT @maxRows
    """


def build_whatsapp_ticket_logs_query() -> str:
    return f"""
      WITH source_rows AS (
        SELECT
          'whatsapp_ticket_log' AS source_type,
          TO_HEX(SHA256(CONCAT(
            IFNULL(CAST(source_year AS STRING), ''),
            '|', IFNULL(CAST(source_table AS STRING), ''),
            '|', IFNULL(CAST(reported_date AS STRING), ''),
            '|', IFNULL(CAST(organisation_id AS STRING), ''),
            '|', IFNULL(issue_description, '')
          ))) AS id,
          TO_HEX(SHA256(CONCAT(
            IFNULL(CAST(source_year AS STRING), ''),
            '|', IFNULL(CAST(source_table AS STRING), ''),
            '|', IFNULL(CAST(reported_date AS STRING), ''),
            '|', IFNULL(CAST(organisation_id AS STRING), ''),
            '|', IFNULL(issue_description, '')
          ))) AS ticket_id,
          CAST(NULL AS STRING) AS part_id,
          category AS title,
          issue_description AS body,
          ticket_type AS tags,
          ticket_status AS state,
          LOWER(IFNULL(ticket_status, '')) NOT IN ('closed', 'done', 'resolved') AS open,
          CAST(NULL AS STRING) AS team_assignee_id,
          CAST(NULL AS STRING) AS admin_assignee_id,
          SAFE_CAST(reported_date AS TIMESTAMP) AS created_at,
          SAFE_CAST(reported_date AS TIMESTAMP) AS updated_at,
          CAST(NULL AS STRING) AS conversation_id,
          CAST(NULL AS STRING) AS hubspot_company_id,
          reported_customer AS company_name,
          CAST(organisation_id AS STRING) AS organisation_id,
          COALESCE(organisation_name, organisation) AS organisation_name,
          CAST(NULL AS STRING) AS intercom_company_id,
          CAST(NULL AS STRING) AS intercom_company_name,
          CAST(NULL AS STRING) AS intercom_user_id,
          CAST(NULL AS STRING) AS intercom_user_external_id,
          CAST(NULL AS STRING) AS intercom_user_email,
          CAST(NULL AS STRING) AS intercom_user_name,
          slack_link,
          investigation_ticket,
          bug_ticket,
          priority,
          bug_status,
          fix_versions,
          reported_date_raw
        FROM {bigquery_table_ref(whatsapp_bigquery_view(), bigquery_project())}
        WHERE is_whatsapp
          AND SAFE_CAST(reported_date AS TIMESTAMP) >= @windowStart
          AND SAFE_CAST(reported_date AS TIMESTAMP) < @windowEnd
      ),
      scored_rows AS (
        SELECT
          *,
          LOWER(CONCAT(
            IFNULL(CAST(title AS STRING), ''),
            ' ',
            IFNULL(CAST(body AS STRING), ''),
            ' ',
            IFNULL(CAST(tags AS STRING), ''),
            ' ',
            IFNULL(CAST(state AS STRING), ''),
            ' ',
            IFNULL(CAST(company_name AS STRING), ''),
            ' ',
            IFNULL(CAST(organisation_name AS STRING), '')
          )) AS candidate_text
        FROM source_rows
      ),
      candidate_rows AS (
        SELECT
          *,
          IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}'), 1, 0) AS problem_score,
          IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_NOISE_PATTERN}'), 1, 0) AS noise_score,
          (
            IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}'), 10, 0)
            + IF(REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PRODUCT_PATTERN}'), 3, 0)
            + IF(REGEXP_CONTAINS(candidate_text, r'\\b(blocked|down|outage|cannot|unable|failed)\\b'), 5, 0)
          ) AS candidate_score,
          CASE
            WHEN REGEXP_CONTAINS(candidate_text, r'\\b(blocked|down|outage|cannot|unable|failed)\\b') THEN 'high_severity_problem_keyword'
            WHEN REGEXP_CONTAINS(candidate_text, r'{SUPPORT_PROBLEM_PATTERN}') THEN 'problem_keyword'
            ELSE 'not_candidate'
          END AS candidate_reason
        FROM scored_rows
      )
      SELECT * EXCEPT(candidate_text, problem_score, noise_score, reported_date_raw)
      FROM candidate_rows
      WHERE problem_score > 0
        AND noise_score = 0
      ORDER BY candidate_score DESC, updated_at DESC NULLS LAST, created_at DESC NULLS LAST
      LIMIT @maxRows
    """


def build_intercom_counts_query() -> str:
    project = bigquery_project()
    conversations_table = bigquery_table_ref(f"{intercom_bigquery_dataset()}.conversations", project)
    parts_table = bigquery_table_ref(f"{intercom_bigquery_dataset()}.conversation_parts", project)
    return f"""
      SELECT
        (
          SELECT COUNT(DISTINCT id)
          FROM {conversations_table}
          WHERE _PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 2 DAY)
            AND (
              (SAFE_CAST(created_at AS TIMESTAMP) >= @windowStart AND SAFE_CAST(created_at AS TIMESTAMP) < @windowEnd)
              OR (SAFE_CAST(updated_at AS TIMESTAMP) >= @windowStart AND SAFE_CAST(updated_at AS TIMESTAMP) < @windowEnd)
            )
        ) AS total_conversations,
        (
          SELECT COUNT(DISTINCT id)
          FROM {parts_table}
          WHERE _PARTITIONTIME >= TIMESTAMP_SUB(@windowStart, INTERVAL 2 DAY)
            AND SAFE_CAST(created_at AS TIMESTAMP) >= @windowStart
            AND SAFE_CAST(created_at AS TIMESTAMP) < @windowEnd
        ) AS total_conversation_parts
    """


def build_whatsapp_counts_query() -> str:
    return f"""
      SELECT COUNT(1) AS total_whatsapp_rows
      FROM {bigquery_table_ref(whatsapp_bigquery_view(), bigquery_project())}
      WHERE is_whatsapp
        AND SAFE_CAST(reported_date AS TIMESTAMP) >= @windowStart
        AND SAFE_CAST(reported_date AS TIMESTAMP) < @windowEnd
    """


def bigquery_params(window_start: datetime, window_end: datetime, max_rows: int) -> dict[str, tuple[str, str]]:
    return {
        "windowStart": ("TIMESTAMP", isoformat(window_start)),
        "windowEnd": ("TIMESTAMP", isoformat(window_end)),
        "maxRows": ("INT64", str(max_rows)),
    }


def int_value(value: Any) -> int:
    try:
        return int(str(value or "0"))
    except (TypeError, ValueError):
        return 0


def search_bigquery_support_items(
    window_start: datetime,
    window_end: datetime,
    max_items: int = DEFAULT_MAX_SUPPORT_ITEMS,
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    if (os.environ.get("LAUNCHBOT_SUPPORT_WATCH_SOURCE", DEFAULT_SUPPORT_WATCH_SOURCE).strip().lower() or DEFAULT_SUPPORT_WATCH_SOURCE) != "bigquery":
        raise LaunchbotSupportWatchError("Unsupported support-watch source. Set LAUNCHBOT_SUPPORT_WATCH_SOURCE=bigquery.")
    params = bigquery_params(window_start, window_end, max_items)
    source_status: dict[str, dict[str, Any]] = {}
    try:
        intercom_counts = run_bigquery_query(build_intercom_counts_query(), params, project=bigquery_project())
        intercom_count_row = intercom_counts[0] if intercom_counts else {}
        total_conversations = int_value(intercom_count_row.get("total_conversations"))
        total_conversation_parts = int_value(intercom_count_row.get("total_conversation_parts"))
        intercom_rows = run_bigquery_query(build_intercom_conversations_query(), params, project=bigquery_project())
        source_status["intercom_conversations"] = {
            "status": "verified",
            "source": "bigquery",
            "table": f"{bigquery_project()}.{intercom_bigquery_dataset()}.conversations",
            "parts_table": f"{bigquery_project()}.{intercom_bigquery_dataset()}.conversation_parts",
            "row_count": len(intercom_rows),
            "fetched_row_count": len(intercom_rows),
            "candidate_row_count": len(intercom_rows),
            "total_conversations": total_conversations,
            "total_conversation_parts": total_conversation_parts,
            "total_matching_rows": total_conversations + total_conversation_parts,
            "limit": max_items,
            "hit_limit": len(intercom_rows) >= max_items,
        }
    except LaunchbotSupportWatchError as error:
        source_status["intercom_conversations"] = {
            "status": "blocked",
            "source": "bigquery",
            "table": f"{bigquery_project()}.{intercom_bigquery_dataset()}.conversations",
            "row_count": 0,
            "error": safe_error(str(error)),
        }
        raise LaunchbotSupportWatchError(f"BigQuery Intercom conversations source unavailable: {error}") from error

    rows = list(intercom_rows)
    if include_whatsapp_source():
        try:
            whatsapp_counts = run_bigquery_query(build_whatsapp_counts_query(), params, project=bigquery_project())
            whatsapp_total = int_value((whatsapp_counts[0] if whatsapp_counts else {}).get("total_whatsapp_rows"))
            whatsapp_rows = run_bigquery_query(
                build_whatsapp_ticket_logs_query(),
                bigquery_params(window_start, window_end, max_items),
                project=bigquery_project(),
            )
            rows.extend(whatsapp_rows)
            source_status["whatsapp_ticket_logs"] = {
                "status": "verified",
                "source": "bigquery",
                "table": f"{bigquery_project()}.{whatsapp_bigquery_view()}",
                "row_count": len(whatsapp_rows),
                "fetched_row_count": len(whatsapp_rows),
                "candidate_row_count": len(whatsapp_rows),
                "total_matching_rows": whatsapp_total,
                "limit": max_items,
                "hit_limit": len(whatsapp_rows) >= max_items,
            }
        except LaunchbotSupportWatchError as error:
            source_status["whatsapp_ticket_logs"] = {
                "status": "blocked",
                "source": "bigquery",
                "table": f"{bigquery_project()}.{whatsapp_bigquery_view()}",
                "row_count": 0,
                "error": safe_error(str(error)),
            }
    elif not include_whatsapp_source():
        source_status["whatsapp_ticket_logs"] = {
            "status": "skipped",
            "source": "bigquery",
            "table": f"{bigquery_project()}.{whatsapp_bigquery_view()}",
            "row_count": 0,
        }
    rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    return rows[:max_items], source_status


def support_item_url(row: dict[str, Any]) -> str:
    source_type = str(row.get("source_type") or "")
    if source_type.startswith("intercom"):
        return intercom_conversation_url(str(row.get("conversation_id") or row.get("ticket_id") or ""))
    for key in ("slack_link", "bug_ticket", "investigation_ticket"):
        value = str(row.get(key) or "").strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        jira_url = jira_issue_url(value)
        if jira_url:
            return jira_url
    return ""


def source_ref(row: dict[str, Any]) -> str:
    source_type = str(row.get("source_type") or "")
    if source_type == "intercom_conversation_part" and row.get("part_id"):
        return f"intercom.conversation_parts:{row.get('part_id')}"
    if source_type == "intercom_conversation" and row.get("conversation_id"):
        return f"intercom.conversations:{row.get('conversation_id')}"
    if source_type == "whatsapp_ticket_log":
        return f"whatsapp.ticket_logs:{row.get('id')}"
    return str(row.get("id") or "")


def normalize_support_item(raw: dict[str, Any]) -> dict[str, Any]:
    source_type = str(raw.get("source_type") or "support_signal")
    title = raw.get("title") or raw.get("category") or ""
    body = raw.get("body") or raw.get("summary") or ""
    tags = raw.get("tags") or ""
    state = raw.get("state") or raw.get("ticket_status") or ""
    item_id = str(raw.get("id") or raw.get("ticket_id") or "")
    public_id = str(raw.get("ticket_id") or item_id)
    company = raw.get("company_name") or raw.get("organisation_name") or raw.get("intercom_company_name") or ""
    text = safe_text(f"{title}. {body}. {tags}. {company}", 900)
    return {
        "id": item_id,
        "ticket_id": public_id,
        "source_type": source_type,
        "source_ref": source_ref(raw),
        "title": safe_text(title, 180),
        "summary": safe_text(text, 320),
        "state": safe_text(state, 80),
        "open": bool(raw.get("open", True)),
        "team_assignee_id": str(raw.get("team_assignee_id") or ""),
        "admin_assignee_id": str(raw.get("admin_assignee_id") or ""),
        "created_at": str(raw.get("created_at") or ""),
        "updated_at": str(raw.get("updated_at") or ""),
        "source_url": support_item_url(raw),
        "hubspot_company_id": str(raw.get("hubspot_company_id") or ""),
        "company_name": safe_text(raw.get("company_name") or "", 120),
        "organisation_id": str(raw.get("organisation_id") or ""),
        "organisation_name": safe_text(raw.get("organisation_name") or "", 120),
        "search_text": safe_text(text, 900).lower(),
    }


def product_area_for_text(text: str) -> str:
    lowered = text.lower()
    best_area = "StaffAny"
    best_hits = 0
    for area, hints in PRODUCT_HINTS.items():
        hits = sum(1 for hint in hints if hint in lowered)
        if hits > best_hits:
            best_area = area
            best_hits = hits
    return best_area


def error_signature(text: str) -> str:
    matches = list(ERROR_SIGNATURE_RE.finditer(text))
    if not matches:
        return ""

    def normalize_signature(raw: str) -> str:
        signature = safe_text(raw, 100).lower()
        signature = re.sub(r"\[(?:email|phone)\]", " ", signature)
        signature = re.sub(r"\b(customer|user|team|please|ticket|support|for)\b", " ", signature)
        return re.sub(r"\s+", " ", signature).strip(" .:-")

    for match in matches:
        candidate = normalize_signature(match.group(0))
        if re.search(r"\b(cannot|unable|failed|failure|error)\b", candidate):
            return candidate
    signature = normalize_signature(matches[0].group(0))
    signature = re.sub(r"\[(?:email|phone)\]", " ", signature)
    signature = re.sub(r"\b(customer|user|team|please|ticket|support|for)\b", " ", signature)
    return re.sub(r"\s+", " ", signature).strip(" .:-")


def topic_tokens(text: str) -> list[str]:
    lowered = text.lower()
    tokens = [token for token in re.findall(r"[a-z0-9]{3,}", lowered) if token not in STOP_WORDS]
    product_terms = []
    for hints in PRODUCT_HINTS.values():
        for hint in hints:
            if hint in lowered:
                product_terms.append(hint.replace(" ", "_"))
    ordered = []
    for token_item in [*product_terms, *tokens]:
        if token_item not in ordered:
            ordered.append(token_item)
    return ordered[:8]


def finding_signature(product_area: str, tokens: list[str], signature: str) -> str:
    base = "|".join([product_area.lower(), signature]) if signature else "|".join([product_area.lower(), "topic", *tokens[:4]])
    return re.sub(r"[^a-z0-9|_]+", "", base)


def ordered_unique(values: list[str], limit: int) -> list[str]:
    result = []
    for value in values:
        cleaned = str(value or "").strip()
        if cleaned and cleaned not in result:
            result.append(cleaned)
        if len(result) >= limit:
            break
    return result


def cluster_support_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_support_item(item) for item in items]
    groups: dict[str, list[dict[str, Any]]] = {}
    group_meta: dict[str, dict[str, Any]] = {}
    for ticket in normalized:
        text = ticket["search_text"]
        area = product_area_for_text(text)
        signature = error_signature(text)
        tokens = topic_tokens(text)
        key = finding_signature(area, tokens, signature)
        groups.setdefault(key, []).append(ticket)
        group_meta.setdefault(key, {"product_area": area, "error_signature": signature, "tokens": tokens})

    findings: list[dict[str, Any]] = []
    for key, items in groups.items():
        meta = group_meta[key]
        combined = " ".join(item["search_text"] for item in items)
        repeated_topic = len(items) >= 3
        shared_error = bool(meta["error_signature"] and len(items) >= 2)
        high_severity = bool(HIGH_SEVERITY_RE.search(combined))
        if not (repeated_topic or shared_error or high_severity):
            continue
        severity = "high" if high_severity else "medium"
        signal = "high_severity_blocker" if high_severity and len(items) == 1 else "shared_error_phrase" if shared_error else "repeated_topic"
        sample_titles = [item["title"] or item["summary"] for item in items[:MAX_SAFE_TICKETS_PER_FINDING]]
        summary_seed = meta["error_signature"] or " / ".join(meta["tokens"][:3]) or sample_titles[0]
        findings.append(
            {
                "signature": key,
                "status": STATE_STATUS_NEW,
                "summary": safe_text(f"{meta['product_area']} support signal: {summary_seed}", 180),
                "product_area": meta["product_area"],
                "severity": severity,
                "signal": signal,
                "ticket_count": len(items),
                "ticket_ids": ordered_unique([item["ticket_id"] or item["id"] for item in items if item.get("id")], MAX_SAFE_TICKETS_PER_FINDING),
                "evidence_tickets": [
                    {
                        "id": item["id"],
                        "ticket_id": item["ticket_id"],
                        "source_type": item["source_type"],
                        "source_ref": item["source_ref"],
                        "title": item["title"],
                        "summary": item["summary"],
                        "state": item["state"],
                        "team_assignee_id": item["team_assignee_id"],
                        "admin_assignee_id": item["admin_assignee_id"],
                        "created_at": item["created_at"],
                        "updated_at": item["updated_at"],
                        "source_url": item["source_url"],
                        "hubspot_company_id": item["hubspot_company_id"],
                        "company_name": item["company_name"],
                        "organisation_id": item["organisation_id"],
                        "organisation_name": item["organisation_name"],
                    }
                    for item in items[:MAX_SAFE_TICKETS_PER_FINDING]
                ],
                "search_terms": meta["tokens"][:6],
                "error_signature": meta["error_signature"],
                "confidence": "needs-check" if high_severity and len(items) == 1 else "verified",
            }
        )
    findings.sort(key=lambda item: (item["severity"] != "high", -int(item["ticket_count"]), item["summary"]))
    return findings[:MAX_FINDINGS]


def cluster_tickets(tickets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return cluster_support_items(tickets)


def pantheon_repo_dir() -> Path:
    configured = os.environ.get("LAUNCHBOT_PANTHEON_REPO_DIR", "").strip()
    candidates = [
        configured,
        os.path.expanduser("~/.hermes/profiles/launchbot/source/pantheon"),
        "/Users/leekaiyi/workspace/pantheon",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).expanduser().exists():
            return Path(candidate).expanduser()
    return Path(configured or os.path.expanduser("~/.hermes/profiles/launchbot/source/pantheon")).expanduser()


def run_command(args: list[str], cwd: Path, timeout: int = 10) -> tuple[int, str]:
    try:
        result = subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    return result.returncode, result.stdout[:4000]


def trace_code_evidence(finding: dict[str, Any]) -> dict[str, Any]:
    repo = pantheon_repo_dir()
    if not repo.exists():
        return {"status": "needs-check", "repo": str(repo), "matches": [], "recent_changes": [], "caveat": "Pantheon checkout missing."}
    status_code, status_out = run_command(["git", "status", "--short"], repo)
    branch_code, branch_out = run_command(["git", "rev-parse", "--abbrev-ref", "HEAD"], repo)
    sha_code, sha_out = run_command(["git", "rev-parse", "HEAD"], repo)
    dirty = bool(status_out.strip()) if status_code == 0 else True
    terms = [term.replace("_", " ") for term in finding.get("search_terms", [])[:4] if len(term) >= 3]
    matches: list[dict[str, str]] = []
    rg = shutil.which("rg")
    if rg and terms:
        pattern = "|".join(re.escape(term) for term in terms[:4])
        code, out = run_command([rg, "-n", "-i", "--max-count", "2", pattern, "apps"], repo, timeout=15)
        if code in {0, 1}:
            for line in out.splitlines()[:8]:
                parts = line.split(":", 2)
                if len(parts) == 3:
                    matches.append({"path": parts[0], "line": parts[1], "snippet": safe_text(parts[2], 160)})
    recent_changes: list[str] = []
    if terms:
        grep = "|".join(terms[:3])
        code, out = run_command(["git", "log", "--since=14 days ago", "--oneline", "--regexp-ignore-case", "--grep", grep, "--all", "--max-count", "5"], repo, timeout=10)
        if code == 0:
            recent_changes = [safe_text(line, 180) for line in out.splitlines()[:5]]
    return {
        "status": "needs-check" if dirty else "verified",
        "repo": str(repo),
        "branch": safe_text(branch_out, 80) if branch_code == 0 else "",
        "sha": safe_text(sha_out, 80) if sha_code == 0 else "",
        "dirty": dirty,
        "matches": matches,
        "recent_changes": recent_changes,
        "caveat": "Pantheon checkout is dirty; code trace needs review." if dirty else "Trace is heuristic; engineer review required before root-cause claim.",
    }


def parse_list(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[\s,]+", value or "") if item.strip()]


def fetch_slack_dedupe_texts(window_start: datetime) -> tuple[list[dict[str, str]], str]:
    channel_ids = parse_list(os.environ.get("LAUNCHBOT_SUPPORT_WATCH_DEDUPE_CHANNEL_IDS", ""))
    if not channel_ids:
        return [], "skipped:no-dedupe-channel-configured"
    results: list[dict[str, str]] = []
    oldest = str(unix_timestamp(window_start))
    try:
        for channel_id in channel_ids:
            payload = slack_api("conversations.history", {"channel": channel_id, "oldest": oldest, "limit": 100, "inclusive": "true"})
            for message in payload.get("messages", []) or []:
                if not isinstance(message, dict):
                    continue
                text = safe_text(message.get("text", ""), 500)
                if text:
                    results.append({"channel_id": channel_id, "ts": str(message.get("ts") or ""), "text": text})
    except LaunchbotSupportWatchError as error:
        return results, f"blocked:{safe_error(str(error))}"
    return results, "verified"


def fetch_edt_issues() -> tuple[list[dict[str, str]], str]:
    jql = os.environ.get("LAUNCHBOT_SUPPORT_WATCH_EDT_JQL", DEFAULT_EDT_JQL).strip() or DEFAULT_EDT_JQL
    try:
        payload = jira_post(
            "/rest/api/3/search/jql",
            {
                "jql": jql,
                "maxResults": 50,
                "fields": ["summary", "status", "updated", "description"],
            },
        )
    except LaunchbotSupportWatchError as error:
        return [], f"blocked:{safe_error(str(error))}"
    issues = []
    for issue in payload.get("issues", []) or []:
        fields = issue.get("fields") or {}
        status = fields.get("status") or {}
        issues.append(
            {
                "key": str(issue.get("key") or ""),
                "summary": safe_text(fields.get("summary") or "", 220),
                "status": safe_text(status.get("name") or "", 80),
                "url": f"{jira_base_url()}/browse/{issue.get('key')}" if issue.get("key") else "",
            }
        )
    return issues, "verified"


def overlap_score(needle_terms: list[str], haystack: str) -> int:
    lowered = haystack.lower()
    return sum(1 for term in needle_terms if term and term.replace("_", " ") in lowered)


def dedupe_findings(findings: list[dict[str, Any]], window_start: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    slack_texts, slack_status = fetch_slack_dedupe_texts(window_start)
    edt_issues, edt_status = fetch_edt_issues()
    new_findings: list[dict[str, Any]] = []
    deduped_findings: list[dict[str, Any]] = []
    for finding in findings:
        terms = [str(term).replace("_", " ") for term in finding.get("search_terms", [])[:5]]
        ticket_ids = [str(ticket_id) for ticket_id in finding.get("ticket_ids", []) if ticket_id]
        duplicate = None
        for item in slack_texts:
            text = item["text"].lower()
            if any(ticket_id and ticket_id in text for ticket_id in ticket_ids) or overlap_score(terms, text) >= 2:
                duplicate = {"source": "slack", "channel_id": item["channel_id"], "ts": item["ts"]}
                break
        if not duplicate:
            for issue in edt_issues:
                haystack = f"{issue.get('key')} {issue.get('summary')} {issue.get('status')}".lower()
                if any(ticket_id and ticket_id in haystack for ticket_id in ticket_ids) or overlap_score(terms, haystack) >= 2:
                    duplicate = {"source": "edt", "issue_key": issue["key"], "url": issue["url"], "summary": issue["summary"]}
                    break
        if duplicate:
            finding["status"] = STATE_STATUS_DEDUPED
            finding["dedupe_match"] = duplicate
            deduped_findings.append(finding)
        else:
            finding["status"] = STATE_STATUS_NEW
            new_findings.append(finding)
    return new_findings, deduped_findings, {"slack": slack_status, "edt": edt_status}


def build_slack_report(report: dict[str, Any]) -> str:
    window = report["window"]
    new_findings = report["new_findings"]
    deduped = report["deduped_findings"]
    if not new_findings:
        return (
            "Launchbot automation: Weekly support watch found no new untracked production-bug signals.\n"
            f"Window: {window['start']} to {window['end']}\n"
            f"Deduped existing: {len(deduped)}\n"
            "Source: BigQuery Intercom conversations + WhatsApp support logs + duty-channel/EDT dedupe\n"
            "Caveat: Report-only. No tickets, assignments, or engineer tags were created."
        )
    lines = [
        "Launchbot automation: Weekly support watch found new production-bug signals.",
        f"Window: {window['start']} to {window['end']}",
        f"New: {len(new_findings)} | Already tracked: {len(deduped)}",
    ]
    for index, finding in enumerate(new_findings[:5], start=1):
        lines.append(f"{index}. [{finding['severity']}] {finding['summary']} ({finding['ticket_count']} support signal{'s' if finding['ticket_count'] != 1 else ''})")
        lines.append(f"   Evidence: {', '.join(finding.get('ticket_ids') or []) or 'ticket ids unavailable'}")
        trace = finding.get("code_trace") or {}
        matches = trace.get("matches") or []
        if matches:
            first = matches[0]
            lines.append(f"   Code trace: {first.get('path')}:{first.get('line')} ({trace.get('status')})")
        else:
            lines.append(f"   Code trace: {trace.get('status', 'needs-check')}")
    lines.extend(
        [
            "Action: review in this channel before forwarding or creating an engineering ticket.",
            "Caveat: Report-only. Launchbot did not create tickets, assign owners, or tag engineers.",
        ]
    )
    return "\n".join(lines)


def report_signature(findings: list[dict[str, Any]]) -> str:
    return "|".join(sorted(str(item.get("signature") or "") for item in findings if item.get("signature")))


def preview_weekly_support_watch_report(
    window_start_iso: str = "",
    window_end_iso: str = "",
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    max_tickets: int = DEFAULT_MAX_SUPPORT_ITEMS,
    include_traces: bool = True,
) -> dict[str, Any]:
    end = parse_iso(window_end_iso, now_utc())
    start = parse_iso(window_start_iso, end - timedelta(days=max(1, int(lookback_days or DEFAULT_LOOKBACK_DAYS))))
    max_count = max(1, min(int(max_tickets or DEFAULT_MAX_SUPPORT_ITEMS), 200))
    scope_data = scope(start, end, max_count)
    try:
        raw_items, source_status = search_bigquery_support_items(start, end, max_count)
    except LaunchbotSupportWatchError as error:
        return blocked(str(error), "BigQuery support-source query", scope_data)

    findings = cluster_support_items(raw_items)
    if include_traces:
        for finding in findings:
            finding["code_trace"] = trace_code_evidence(finding)
    new_findings, deduped_findings, dedupe_sources = dedupe_findings(findings, start)
    report = {
        "window": {"start": isoformat(start), "end": isoformat(end)},
        "ticket_count": len(raw_items),
        "support_item_count": len(raw_items),
        "source_status": source_status,
        "finding_count": len(findings),
        "new_findings": new_findings,
        "deduped_findings": deduped_findings,
        "dedupe_sources": dedupe_sources,
        "report_signature": report_signature(new_findings),
        "will_post_message": False,
        "will_create_ticket": False,
        "will_tag_engineer": False,
        "raw_transcript_persisted": False,
    }
    report["slack_report"] = build_slack_report(report)
    return {
        "answer": report,
        "source": "BigQuery Intercom conversations + WhatsApp support logs + Slack history dedupe + Jira EDT search + Pantheon local trace",
        "scope": scope_data,
        "confidence": "verified" if new_findings else "needs-check",
        "caveat": "Report-only preview. No Slack post, ticket creation, assignment, or engineer tag was performed.",
    }


def resolve_slack_channel_id(channel_name: str) -> str:
    target = (channel_name or "").strip().lstrip("#")
    if not target:
        return ""
    cursor = ""
    while True:
        payload = slack_api(
            "conversations.list",
            {
                "types": "public_channel,private_channel",
                "limit": 200,
                "cursor": cursor,
                "exclude_archived": "true",
            },
        )
        for channel in payload.get("channels", []) or []:
            if str(channel.get("name") or "") == target:
                return str(channel.get("id") or "")
        cursor = str((payload.get("response_metadata") or {}).get("next_cursor") or "")
        if not cursor:
            break
    return ""
