#!/usr/bin/env python3
"""Deterministic BigQuery churn reporting chase for current quarter plus next two quarters."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_TIMEZONE = "Asia/Singapore"
DEFAULT_BQ_PROJECT = "staffany-warehouse"
DEFAULT_BQ_DATASET = "analytics"
DEFAULT_CHANNEL_ID = "C019RVCR4S1"
DEFAULT_MAX_BYTES_BILLED = "50000000000"
DEFAULT_MAX_ROWS = 25
SILENT_PREFIX = "[SILENT] PSM Ops automation"
CHURN_PROJECTION_SQL_NAME = "psm_ops_churn_projection_dashboard_292.sql"
CHURN_PROJECTION_DASHBOARD_URL = (
    "https://metabase.staffany.com/dashboard/292-churn-projection-dashboard"
    "?churn_class=1-Actualized"
    "&churn_class=2-Non-Actualized+%2850%25+Confirmed%29"
    "&churn_class=2-Non-Actualized+%28Confirmed%29"
    "&churn_class=3-Non-Actualized+%28Overdue%29"
    "&churn_class=4-Non-Actualized+%28Red%29"
    "&churn_class=5-Non-Actualized+%28Orange%29"
    "&location=&renewal_date_filter=2026-01-01~2026-03-31"
)
UPCOMING_RENEWALS_DASHBOARD_URL = "https://metabase.staffany.com/dashboard/5029-upcoming-renewals-dashboard?renewal_quarter=26Q2"
IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_-]+$")


class ChurnReportingError(RuntimeError):
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
        raise ChurnReportingError("PSM_OPS_TIMEZONE must be a valid IANA timezone.") from error


def _parse_as_of(value: str, local_timezone: ZoneInfo) -> datetime:
    if not value:
        return datetime.now(local_timezone)
    raw = value.strip()
    if len(raw) == 10:
        try:
            parsed_date = date.fromisoformat(raw)
        except ValueError as error:
            raise ChurnReportingError("as_of must be ISO date or timestamp.") from error
        return datetime.combine(parsed_date, datetime.min.time(), tzinfo=local_timezone)
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise ChurnReportingError("as_of must be ISO date or timestamp.") from error
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=local_timezone)
    return parsed.astimezone(local_timezone)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the weekly PSM churn reporting chase from BigQuery.")
    parser.add_argument("--as-of", default="", help="ISO date/timestamp. Defaults to now in Asia/Singapore.")
    parser.add_argument("--dry-run", action="store_true", help="Mark output as a dry run. No writes are ever performed.")
    parser.add_argument("--max-rows", type=int, default=DEFAULT_MAX_ROWS, help="Maximum row examples per section.")
    return parser.parse_args(argv)


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, 1)


def quarter_start(value: date) -> date:
    return date(value.year, ((value.month - 1) // 3) * 3 + 1, 1)


def quarter_label(value: date) -> str:
    return f"{value.year % 100:02d}Q{((value.month - 1) // 3) + 1}"


def reporting_window(as_of: datetime) -> dict[str, Any]:
    start = quarter_start(as_of.date())
    end = _add_months(start, 9)
    quarters = [quarter_label(_add_months(start, offset)) for offset in (0, 3, 6)]
    return {"start": start, "end": end, "quarters": quarters}


def _identifier(value: str, label: str) -> str:
    raw = value.strip()
    if not raw or not IDENTIFIER_RE.fullmatch(raw):
        raise ChurnReportingError(f"{label} must be a simple BigQuery identifier.")
    return raw


def _table(project: str, dataset: str, table_name: str) -> str:
    safe_project = _identifier(project, "BigQuery project")
    safe_dataset = _identifier(dataset, "BigQuery dataset")
    safe_table = _identifier(table_name, "BigQuery table")
    return f"`{safe_project}.{safe_dataset}.{safe_table}`"


def _bq_project() -> str:
    return _env("PSM_OPS_CHURN_REPORTING_BQ_PROJECT", DEFAULT_BQ_PROJECT) or DEFAULT_BQ_PROJECT


def _bq_dataset() -> str:
    return _env("PSM_OPS_CHURN_REPORTING_BQ_DATASET", DEFAULT_BQ_DATASET) or DEFAULT_BQ_DATASET


def _metabase_churn_url() -> str:
    return _env("PSM_OPS_CHURN_REPORTING_CHURN_DASHBOARD_URL", CHURN_PROJECTION_DASHBOARD_URL) or CHURN_PROJECTION_DASHBOARD_URL


def _metabase_renewals_url() -> str:
    return _env("PSM_OPS_CHURN_REPORTING_RENEWALS_DASHBOARD_URL", UPCOMING_RENEWALS_DASHBOARD_URL) or UPCOMING_RENEWALS_DASHBOARD_URL


def _channel_id() -> str:
    return _env("PSM_OPS_CHURN_REPORTING_CHANNEL_ID", DEFAULT_CHANNEL_ID) or DEFAULT_CHANNEL_ID


def _dashboard_sql_path() -> Path:
    script_path = Path(__file__).resolve()
    candidates = [
        script_path.parent.parent / "sql" / CHURN_PROJECTION_SQL_NAME,
        script_path.parent.parent / "runtime" / "sql" / CHURN_PROJECTION_SQL_NAME,
        _profile_dir() / "runtime" / "sql" / CHURN_PROJECTION_SQL_NAME,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise ChurnReportingError(f"Dashboard 292 SQL file missing: {CHURN_PROJECTION_SQL_NAME}")


def dashboard_292_source_sql(project: str | None = None, dataset: str | None = None) -> str:
    path = _dashboard_sql_path()
    sql = path.read_text(encoding="utf-8").strip().rstrip(";")
    forbidden = [
        "13UjJOZpkyngN_5oo4LtzeJWfqhc7PAD8hR1E_" + "aU6gP0",
        "spreadsheets" + ".values",
        "googleapis.com/" + "sheets",
        "gs" + "pread",
    ]
    for text in forbidden:
        if text in sql:
            raise ChurnReportingError(f"Dashboard SQL contains forbidden sheet source text: {text}")
    selected_project = project or _bq_project()
    selected_dataset = dataset or _bq_dataset()
    safe_project = _identifier(selected_project, "BigQuery project")
    safe_dataset = _identifier(selected_dataset, "BigQuery dataset")
    sql = re.sub(r"`analytics\.([A-Za-z0-9_]+)`", rf"`{safe_project}.{safe_dataset}.\1`", sql)
    sql = re.sub(r"(?<![`A-Za-z0-9_.-])analytics\.([A-Za-z0-9_]+)", rf"`{safe_project}.{safe_dataset}.\1`", sql)
    return sql


def build_dashboard_292_query(as_of: datetime, project: str | None = None, dataset: str | None = None) -> str:
    window = reporting_window(as_of)
    source_sql = dashboard_292_source_sql(project=project, dataset=dataset)
    return f"""
SELECT
  CAST(d.company_id AS STRING) AS company_id,
  CAST(d.raw_company_id AS STRING) AS raw_company_id,
  d.company_name,
  d.deal_psm_name,
  d.company_country,
  ROUND(CAST(d.company_mrr AS FLOAT64), 2) AS company_mrr,
  d.deal_start,
  d.deal_end,
  d.renewal_date,
  d.renewingQuarter AS renewal_quarter,
  d.orgNames AS org_names,
  d.minAccountHealth AS min_account_health,
  d.avgAccountHealth AS avg_account_health,
  d.bestAccountHealth AS best_account_health,
  d.auto_assessment,
  d.renewal_assessment,
  d.renewal_assessment_reason,
  d.company_churn_reason,
  d.company_churn_reason_bucket,
  d.last_main_deal_id,
  d.last_main_paid_deal_url,
  d.churn_class,
  ROUND(CAST(d.weighted_churn_mrr AS FLOAT64), 2) AS weighted_churn_mrr
FROM (
{source_sql}
) d
WHERE d.renewal_date >= DATE '{window["start"].isoformat()}'
  AND d.renewal_date < DATE '{window["end"].isoformat()}'
  AND d.churn_class IS NOT NULL
ORDER BY d.renewal_date ASC, d.deal_psm_name ASC, weighted_churn_mrr DESC, d.company_name ASC
""".strip()


def build_upcoming_query(as_of: datetime, project: str | None = None, dataset: str | None = None) -> str:
    window = reporting_window(as_of)
    selected_project = project or _bq_project()
    selected_dataset = dataset or _bq_dataset()
    upcoming = _table(selected_project, selected_dataset, "fct_upcoming_renewal_cycles")
    snapshot = _table(selected_project, selected_dataset, "fct_company_revenue_snapshot")
    churn = _table(selected_project, selected_dataset, "fct_churnmrrbymonth")
    return f"""
WITH params AS (
  SELECT DATE '{window["start"].isoformat()}' AS start_date, DATE '{window["end"].isoformat()}' AS end_date
),
latest_snapshot AS (
  SELECT MAX(snapshot_month) AS snapshot_month
  FROM {snapshot}
),
latest_revenue AS (
  SELECT
    company_id,
    ROUND(CAST(total_mrr AS FLOAT64), 2) AS current_mrr
  FROM {snapshot}
  JOIN latest_snapshot USING (snapshot_month)
),
actualized_churn AS (
  SELECT
    company_id,
    ARRAY_AGG(company_churn_reason IGNORE NULLS ORDER BY churn_date DESC LIMIT 1)[SAFE_OFFSET(0)] AS company_churn_reason,
    ARRAY_AGG(company_churn_reason_bucket IGNORE NULLS ORDER BY churn_date DESC LIMIT 1)[SAFE_OFFSET(0)] AS company_churn_reason_bucket,
    MAX(churn_date) AS latest_churn_date
  FROM {churn}
  GROUP BY company_id
)
SELECT
  r.cycle_key,
  r.cycle_row_type,
  CAST(r.canonical_company_id AS STRING) AS canonical_company_id,
  CAST(r.raw_company_id AS STRING) AS raw_company_id,
  r.company_name,
  r.company_country,
  r.anchor_main_deal_id,
  r.anchor_main_deal_name,
  r.renewal_main_deal_id,
  r.renewal_main_deal_name,
  r.deal_psm_name,
  r.deal_stage,
  r.deal_billing_status,
  r.renewal_date,
  r.deal_start_date,
  r.deal_end_date,
  r.renewal_quarter,
  r.days_to_renewal,
  r.days_since_renewal_start,
  r.renewal_assessment,
  r.renewal_assessment_reason,
  r.renewal_progress_status,
  r.renewal_bucket,
  COALESCE(lr.current_mrr, 0) AS current_mrr,
  ac.company_churn_reason,
  ac.company_churn_reason_bucket,
  ac.latest_churn_date
FROM {upcoming} r
CROSS JOIN params p
LEFT JOIN latest_revenue lr
  ON lr.company_id = COALESCE(NULLIF(r.canonical_company_id, ''), NULLIF(r.raw_company_id, ''))
LEFT JOIN actualized_churn ac
  ON ac.company_id = COALESCE(NULLIF(r.canonical_company_id, ''), NULLIF(r.raw_company_id, ''))
WHERE r.renewal_date >= p.start_date
  AND r.renewal_date < p.end_date
ORDER BY r.renewal_date ASC, r.deal_psm_name ASC, current_mrr DESC, r.company_name ASC
""".strip()


def build_query(as_of: datetime, project: str | None = None, dataset: str | None = None) -> str:
    return build_upcoming_query(as_of, project=project, dataset=dataset)


def _bq_command() -> str:
    configured = _env("BQ_BIN")
    candidates = [configured, "bq", "/opt/homebrew/bin/bq", "/usr/local/bin/bq", "/home/leekaiyi/google-cloud-sdk/bin/bq"]
    for candidate in [item for item in candidates if item]:
        resolved = shutil.which(candidate) if "/" not in candidate else candidate
        if resolved and Path(resolved).exists():
            return resolved
    raise ChurnReportingError("bq CLI not found. Install bq or set BQ_BIN.")


def fetch_bigquery_rows(query: str, timeout_seconds: int = 180) -> list[dict[str, Any]]:
    command = [
        _bq_command(),
        "query",
        "--format=json",
        "--use_legacy_sql=false",
        f"--project_id={_bq_project()}",
        f"--max_rows={max(1, min(int(_env('BQ_MAX_ROWS', '5000') or '5000'), 10000))}",
        f"--maximum_bytes_billed={_env('BQ_MAX_BYTES_BILLED', DEFAULT_MAX_BYTES_BILLED) or DEFAULT_MAX_BYTES_BILLED}",
        query,
    ]
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "unknown BigQuery error").strip().splitlines()[-1]
        raise ChurnReportingError(f"BigQuery query failed: {detail[:300]}")
    try:
        payload = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as error:
        raise ChurnReportingError("BigQuery returned non-JSON output.") from error
    if not isinstance(payload, list):
        raise ChurnReportingError("BigQuery returned an unexpected payload shape.")
    return [row for row in payload if isinstance(row, dict)]


def fetch_churn_rows(as_of: datetime) -> dict[str, list[dict[str, Any]]]:
    return {
        "dashboard_rows": fetch_bigquery_rows(build_dashboard_292_query(as_of), timeout_seconds=240),
        "upcoming_rows": fetch_bigquery_rows(build_upcoming_query(as_of), timeout_seconds=180),
    }


def _text(value: Any) -> str:
    return str(value or "").strip()


def _lower(value: Any) -> str:
    return _text(value).lower()


def _blank_or_generic(value: Any) -> bool:
    text = _lower(value)
    return text in {"", "-", "na", "n/a", "none", "nil", "null", "unknown", "tbc", "tbd", "pending", "other"}


def _float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


DASHBOARD_ACTUALIZED_CHURN_CLASS = "1-Actualized"
UPCOMING_EXCEPTION_TERMS = (
    "at risk",
    "delinquent",
    "late payment",
    "not started",
    "no renewal deal yet",
    "no renewal deal",
    "overdue",
    "unpaid",
)


def _owner(row: dict[str, Any]) -> str:
    return _text(row.get("deal_psm_name")) or "Owner missing"


def _company_keys(row: dict[str, Any]) -> set[str]:
    keys: set[str] = set()
    for field in ("company_id", "canonical_company_id", "raw_company_id"):
        value = _lower(row.get(field))
        if value:
            keys.add(value)
    return keys


def dashboard_company_keys(rows: list[dict[str, Any]]) -> set[str]:
    keys: set[str] = set()
    for row in rows:
        keys.update(_company_keys(row))
    return keys


def dashboard_chase_reason(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    if _owner(row) == "Owner missing":
        reasons.append("owner missing - ask who owns this account")
    churn_class = _text(row.get("churn_class"))
    if churn_class == DASHBOARD_ACTUALIZED_CHURN_CLASS:
        if _blank_or_generic(row.get("company_churn_reason")):
            reasons.append("company churn reason missing")
        if _blank_or_generic(row.get("company_churn_reason_bucket")):
            reasons.append("company churn reason bucket missing")
    else:
        if _blank_or_generic(row.get("renewal_assessment")):
            reasons.append("renewal assessment missing")
        if _blank_or_generic(row.get("renewal_assessment_reason")):
            reasons.append("renewal assessment reason missing")
    return "; ".join(dict.fromkeys(reasons))


def dashboard_needs_chase(row: dict[str, Any]) -> bool:
    if _blank_or_generic(row.get("churn_class")):
        return False
    return bool(dashboard_chase_reason(row))


def upcoming_exception_reason(row: dict[str, Any]) -> str:
    reasons: list[str] = []
    if _owner(row) == "Owner missing":
        reasons.append("owner missing - ask who owns this account")
    status_text = " | ".join(
        [
            _lower(row.get("renewal_progress_status")),
            _lower(row.get("renewal_bucket")),
            _lower(row.get("deal_billing_status")),
            _lower(row.get("deal_stage")),
        ]
    )
    matched_terms = [term for term in UPCOMING_EXCEPTION_TERMS if term in status_text]
    if matched_terms:
        reasons.append("risky/overdue upcoming renewal: " + ", ".join(dict.fromkeys(matched_terms)))
    return "; ".join(dict.fromkeys(reasons))


def upcoming_needs_chase(row: dict[str, Any], dashboard_keys: set[str]) -> bool:
    if _company_keys(row) & dashboard_keys:
        return False
    return "risky/overdue upcoming renewal" in upcoming_exception_reason(row)


def safe_dashboard_row(row: dict[str, Any]) -> dict[str, Any]:
    owner = _owner(row)
    return {
        "section": "dashboard_292",
        "company_name": _text(row.get("company_name")) or "Unnamed company",
        "owner": owner,
        "renewal_quarter": _text(row.get("renewal_quarter")) or "Unknown quarter",
        "renewal_date": _text(row.get("renewal_date")) or "No renewal date",
        "churn_class": _text(row.get("churn_class")) or "Missing churn class",
        "renewal_assessment": _text(row.get("renewal_assessment")) or "Missing assessment",
        "renewal_assessment_reason": _text(row.get("renewal_assessment_reason")) or "Missing assessment reason",
        "company_churn_reason": _text(row.get("company_churn_reason")) or "Missing churn reason",
        "company_churn_reason_bucket": _text(row.get("company_churn_reason_bucket")) or "Missing churn reason bucket",
        "company_mrr": round(_float(row.get("company_mrr")), 2),
        "weighted_churn_mrr": round(_float(row.get("weighted_churn_mrr")), 2),
        "hubspot_url": _text(row.get("last_main_paid_deal_url")),
        "chase_reason": dashboard_chase_reason(row),
    }


def safe_upcoming_row(row: dict[str, Any]) -> dict[str, Any]:
    owner = _owner(row)
    return {
        "section": "upcoming_exception",
        "company_name": _text(row.get("company_name")) or "Unnamed company",
        "owner": owner,
        "renewal_quarter": _text(row.get("renewal_quarter")) or "Unknown quarter",
        "renewal_date": _text(row.get("renewal_date")) or "No renewal date",
        "renewal_progress_status": _text(row.get("renewal_progress_status")) or "Missing progress",
        "renewal_bucket": _text(row.get("renewal_bucket")) or "Missing bucket",
        "renewal_assessment": _text(row.get("renewal_assessment")) or "Missing assessment",
        "deal_stage": _text(row.get("deal_stage")) or "Missing deal stage",
        "deal_billing_status": _text(row.get("deal_billing_status")) or "Missing billing status",
        "current_mrr": round(_float(row.get("current_mrr")), 2),
        "chase_reason": upcoming_exception_reason(row),
    }


def build_result(
    source_rows: dict[str, list[dict[str, Any]]] | list[dict[str, Any]],
    as_of: datetime,
    dry_run: bool,
    max_rows: int,
) -> dict[str, Any]:
    window = reporting_window(as_of)
    if isinstance(source_rows, list):
        dashboard_rows: list[dict[str, Any]] = []
        upcoming_rows = source_rows
    else:
        dashboard_rows = source_rows.get("dashboard_rows", [])
        upcoming_rows = source_rows.get("upcoming_rows", [])
    dashboard_keys = dashboard_company_keys(dashboard_rows)
    dashboard_chase_rows = [safe_dashboard_row(row) for row in dashboard_rows if dashboard_needs_chase(row)]
    upcoming_chase_rows = [
        safe_upcoming_row(row)
        for row in upcoming_rows
        if upcoming_needs_chase(row, dashboard_keys)
    ]
    dashboard_chase_rows.sort(
        key=lambda row: (
            row["renewal_quarter"],
            row["owner"],
            row["churn_class"],
            -row["weighted_churn_mrr"],
            row["company_name"],
        )
    )
    upcoming_chase_rows.sort(key=lambda row: (row["renewal_quarter"], row["owner"], -row["current_mrr"], row["company_name"]))
    return {
        "as_of": as_of.date().isoformat(),
        "dry_run": dry_run,
        "window_start": window["start"].isoformat(),
        "window_end_exclusive": window["end"].isoformat(),
        "quarters": window["quarters"],
        "dashboard_checked": len(dashboard_rows),
        "dashboard_needs_chase": len(dashboard_chase_rows),
        "dashboard_owner_missing": sum(1 for row in dashboard_chase_rows if row["owner"] == "Owner missing"),
        "dashboard_rows": dashboard_chase_rows,
        "dashboard_keys_count": len(dashboard_keys),
        "upcoming_checked": len(upcoming_rows),
        "upcoming_needs_chase": len(upcoming_chase_rows),
        "upcoming_owner_missing": sum(1 for row in upcoming_chase_rows if row["owner"] == "Owner missing"),
        "upcoming_rows": upcoming_chase_rows,
        "max_rows": max(1, max_rows),
        "channel_id": _channel_id(),
    }


def _money(value: float) -> str:
    return f"${value:,.0f}" if value else "$0"


def _group_by_quarter_owner(rows: list[dict[str, Any]]) -> dict[str, dict[str, list[dict[str, Any]]]]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[row["renewal_quarter"]][row["owner"]].append(row)
    return grouped


def _append_dashboard_rows(lines: list[str], result: dict[str, Any]) -> None:
    rows = result["dashboard_rows"]
    if not rows:
        lines.append("*Dashboard 292 churn-risk chase* - 0 rows need cleanup.")
        return
    lines.append(
        f"*Dashboard 292 churn-risk chase* - {len(rows)} rows need cleanup "
        f"({result['dashboard_owner_missing']} owner missing)."
    )
    grouped = _group_by_quarter_owner(rows)
    shown = 0
    max_rows = result["max_rows"]
    for quarter in result["quarters"]:
        owners = grouped.get(quarter, {})
        if not owners:
            continue
        lines.append(f"*{quarter}* - {sum(len(items) for items in owners.values())} dashboard rows")
        for owner in sorted(owners):
            owner_rows = owners[owner]
            lines.append(f"{owner} ({len(owner_rows)})")
            by_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
            for row in owner_rows:
                by_class[row["churn_class"]].append(row)
            for churn_class in sorted(by_class):
                lines.append(f"{churn_class}")
                for row in by_class[churn_class]:
                    if shown >= max_rows:
                        remaining = len(rows) - shown
                        if remaining > 0:
                            lines.append(f"- ...and {remaining} more Dashboard 292 rows not shown due to max-row cap.")
                        return
                    status = (
                        f"assessment: {row['renewal_assessment']} / reason: {row['renewal_assessment_reason']}; "
                        f"churn reason: {row['company_churn_reason']} / bucket: {row['company_churn_reason_bucket']}"
                    )
                    link = f" <{row['hubspot_url']}|HubSpot>" if row["hubspot_url"] else ""
                    lines.append(
                        f"- {row['company_name']} ({row['renewal_date']}, {_money(row['weighted_churn_mrr'])} weighted / "
                        f"{_money(row['company_mrr'])} MRR): {row['chase_reason']}; {status}.{link}"
                    )
                    shown += 1


def _append_upcoming_rows(lines: list[str], result: dict[str, Any]) -> None:
    rows = result["upcoming_rows"]
    if not rows:
        lines.append("*Upcoming renewal exceptions* - 0 risky/overdue rows outside Dashboard 292.")
        return
    lines.append(
        f"*Upcoming renewal exceptions* - {len(rows)} risky/overdue rows not already in Dashboard 292 "
        f"({result['upcoming_owner_missing']} owner missing)."
    )
    grouped = _group_by_quarter_owner(rows)
    shown = 0
    max_rows = result["max_rows"]
    for quarter in result["quarters"]:
        owners = grouped.get(quarter, {})
        if not owners:
            continue
        lines.append(f"*{quarter}* - {sum(len(items) for items in owners.values())} upcoming rows")
        for owner in sorted(owners):
            owner_rows = owners[owner]
            lines.append(f"{owner} ({len(owner_rows)})")
            for row in owner_rows:
                if shown >= max_rows:
                    remaining = len(rows) - shown
                    if remaining > 0:
                        lines.append(f"- ...and {remaining} more upcoming rows not shown due to max-row cap.")
                    return
                status = (
                    f"{row['renewal_bucket']} / {row['renewal_progress_status']} / "
                    f"{row['deal_stage']} / {row['deal_billing_status']}"
                )
                lines.append(
                    f"- {row['company_name']} ({row['renewal_date']}, {_money(row['current_mrr'])} MRR): "
                    f"{row['chase_reason']}; {status}"
                )
                shown += 1


def format_result(result: dict[str, Any]) -> str:
    quarters = ", ".join(result["quarters"])
    total_rows = result["dashboard_needs_chase"] + result["upcoming_needs_chase"]
    if total_rows == 0:
        return (
            f"{SILENT_PREFIX}: churn reporting chase found no cleanup rows for {result['as_of']} "
            f"({quarters}; checked {result['dashboard_checked']} dashboard rows and {result['upcoming_checked']} upcoming rows)."
        )
    dry = " DRY RUN" if result.get("dry_run") else ""
    lines = [
        f"PSM Ops automation: Weekly churn reporting chase{dry} - {result['as_of']}",
        f"Window: {quarters} ({result['window_start']} to {result['window_end_exclusive']} exclusive)",
        "Source: BigQuery Dashboard 292 SQL + `staffany-warehouse.analytics.fct_upcoming_renewal_cycles`",
        f"Reference: <{_metabase_churn_url()}|Churn projection> | <{_metabase_renewals_url()}|Upcoming renewals>",
        (
            f"Summary: Dashboard 292 checked {result['dashboard_checked']} non-null churn-class rows, "
            f"{result['dashboard_needs_chase']} need cleanup; Upcoming checked {result['upcoming_checked']} rows, "
            f"{result['upcoming_needs_chase']} risky/overdue exceptions outside Dashboard 292. "
            f"Owner missing: {result['dashboard_owner_missing'] + result['upcoming_owner_missing']}."
        ),
        (
            "Ask: reply in this thread with renewal status, churn reason/category, evidence link, and confirm source fields are updated. "
            "For `1-Actualized`, fill company churn reason + company churn reason bucket. For other churn classes, fill renewal assessment + renewal assessment reason. "
            "For Owner missing, confirm who owns the account."
        ),
        "",
    ]
    _append_dashboard_rows(lines, result)
    lines.append("")
    _append_upcoming_rows(lines, result)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    load_profile_env()
    args = parse_args(argv or sys.argv[1:])
    try:
        local_timezone = _timezone()
        as_of = _parse_as_of(args.as_of, local_timezone)
        rows = fetch_churn_rows(as_of)
        print(format_result(build_result(rows, as_of, args.dry_run, args.max_rows)))
        return 0
    except ChurnReportingError as error:
        print(
            "\n".join(
                [
                    "PSM Ops automation: Churn reporting chase blocked",
                    "Source: BigQuery Dashboard 292 SQL + renewal marts",
                    "Confidence: blocked",
                    f"Caveat: {error}",
                ]
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
