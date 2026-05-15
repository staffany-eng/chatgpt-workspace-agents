#!/usr/bin/env python3
"""Write-capable Google Sheets MCP adapter for sanitized NurtureAny analyses.

This server writes only table-shaped, Slack-safe / CRM-safe analysis rows into
one shared workbook owned by team@staffany.com. It is separate from the Drive
read-only adapter so presentation/photo reads cannot accidentally mutate Sheets.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from mcp.server.fastmcp import FastMCP

from nurtureany_common.google_oauth import (
    access_token as _google_access_token,
    account_email as _google_account_email,
    is_unresolved_env_placeholder as _google_is_unresolved_env_placeholder,
    profile_file as _google_profile_file,
)
from nurtureany_common.responses import blocked_response, safe_detail as _safe_detail


GOOGLE_SHEETS_API_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
GOOGLE_SHEETS_USER_AGENT = "StaffAny-NurtureAny/1.0 (+https://staffany.com)"
GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
SPREADSHEET_ID_ENV = "NURTUREANY_ANALYSIS_OUTPUT_SPREADSHEET_ID"
TOKEN_FILE_ENV = "GOOGLE_SHEETS_TOKEN_FILE"
CLIENT_SECRET_FILE_ENV = "GOOGLE_SHEETS_CLIENT_SECRET_FILE"
ACCOUNT_EMAIL_ENV = "GOOGLE_SHEETS_ACCOUNT_EMAIL"
GOOGLE_SHEETS_TIMEOUT_SECONDS = 15
RUNS_TAB_NAME = "Runs"
RUNS_HEADER = [
    "idempotency_key",
    "updated_at",
    "analysis_type",
    "title",
    "tab_name",
    "source_permalink",
    "row_count",
    "caller_email",
]
MAX_COLUMNS = 40
MAX_ROWS = 1000
MAX_CELL_CHARS = 500
MAX_TITLE_CHARS = 160
MAX_TAB_NAME_CHARS = 80
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
RAW_TRANSCRIPT_RE = re.compile(r"(?im)^(user|bot|assistant|customer|prospect|ae|rep|agent)\s*:")
UNSAFE_COLUMN_TERMS = (
    "raw",
    "transcript",
    "body",
    "phone",
    "mobile",
    "whatsapp_number",
    "guest_export",
    "attendee_export",
    "guest_list",
    "attendee_list",
    "registration_answer",
    "api_key",
    "secret",
    "token",
)


mcp = FastMCP("google_sheets_nurtureany")


class GoogleSheetsError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class ValidationError(Exception):
    pass


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return blocked_response(message, "Google Sheets", scope)


def _profile_file(env_var: str, default_filename: str):
    return _google_profile_file(env_var, default_filename)


def _account_email() -> str:
    return _google_account_email(ACCOUNT_EMAIL_ENV, DEFAULT_ACCOUNT_EMAIL)


def _access_token() -> str:
    return _google_access_token(
        _profile_file(TOKEN_FILE_ENV, "google-sheets-token.json"),
        _profile_file(CLIENT_SECRET_FILE_ENV, "google-sheets-client-secret.json"),
        {GOOGLE_SHEETS_SCOPE},
        GOOGLE_SHEETS_USER_AGENT,
        GOOGLE_SHEETS_TIMEOUT_SECONDS,
        "Google Sheets",
        GoogleSheetsError,
    )


def _extract_spreadsheet_id(value: str) -> str:
    text = str(value or "").strip()
    if not text or _google_is_unresolved_env_placeholder(text):
        return ""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", text)
    if match:
        return match.group(1)
    return text


def _configured_spreadsheet_id() -> str:
    return _extract_spreadsheet_id(os.environ.get(SPREADSHEET_ID_ENV, ""))


def _spreadsheet_id(requested: str = "") -> str:
    configured = _configured_spreadsheet_id()
    explicit = _extract_spreadsheet_id(requested)
    if configured and explicit and configured != explicit:
        raise ValidationError("Requested spreadsheet_id does not match the configured shared analysis workbook.")
    selected = explicit or configured
    if not selected:
        raise ValidationError(f"{SPREADSHEET_ID_ENV} is required for analysis Sheet exports.")
    return selected


def _spreadsheet_url(spreadsheet_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"


def _sheet_url(spreadsheet_id: str, sheet_id: int | str | None = None) -> str:
    url = _spreadsheet_url(spreadsheet_id)
    if sheet_id not in (None, ""):
        return f"{url}#gid={sheet_id}"
    return url


def _normalized_column_name(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _validate_column_name(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValidationError("Sheet export columns cannot be blank.")
    normalized = _normalized_column_name(text)
    if "email" in normalized and "domain" not in normalized and "hash" not in normalized:
        raise ValidationError(f"Unsafe Sheet export column rejected: {text}. Use email_domain or attendee_hash instead.")
    for term in UNSAFE_COLUMN_TERMS:
        if term in normalized:
            raise ValidationError(f"Unsafe Sheet export column rejected: {text}.")
    return text[:MAX_CELL_CHARS]


def _looks_like_phone(value: str) -> bool:
    text = str(value or "").strip()
    digits = re.sub(r"\D", "", text)
    if len(digits) < 8 or len(digits) > 15:
        return False
    if re.search(r"\b\d{4}-\d{2}-\d{2}\b", text) or re.search(r"\b\d{2}/\d{2}/\d{4}\b", text):
        return False
    if "+" in text:
        return True
    return bool(re.search(r"\b\d{8}\b|\b\d{4}[\s.-]\d{4}\b|\b\d{3}[\s.-]\d{3}[\s.-]\d{4}\b", text))


def _validate_cell(value: Any, column: str) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    text = str(value)
    normalized_column = _normalized_column_name(column)
    if len(text) > MAX_CELL_CHARS:
        raise ValidationError(f"Cell under column {column} is too long for Slack-safe Sheet export.")
    if EMAIL_RE.search(text):
        raise ValidationError(f"Cell under column {column} contains a full email address.")
    if _looks_like_phone(text) and not normalized_column.endswith("_id") and normalized_column not in {"company_id", "hubspot_company_id", "contact_id", "deal_id", "event_id", "object_id"}:
        raise ValidationError(f"Cell under column {column} appears to contain a phone number.")
    if RAW_TRANSCRIPT_RE.search(text) and len(re.findall(r"\n", text)) >= 1:
        raise ValidationError(f"Cell under column {column} looks like a raw transcript.")
    lowered = text.lower()
    if '"properties"' in lowered and ("phone" in lowered or "body" in lowered or "email" in lowered):
        raise ValidationError(f"Cell under column {column} looks like a raw HubSpot row.")
    if text.count("\n") > 5:
        raise ValidationError(f"Cell under column {column} has too many lines for Slack-safe Sheet export.")
    return text


def _infer_columns(rows: list[Any]) -> list[str]:
    columns: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for key in row:
            key_text = str(key or "").strip()
            if key_text and key_text not in columns:
                columns.append(key_text)
    return columns


def _normalize_table(columns: list[Any] | None, rows: list[Any] | None) -> tuple[list[str], list[list[Any]]]:
    source_rows = rows or []
    if not isinstance(source_rows, list):
        raise ValidationError("rows must be a list of objects or arrays.")
    if len(source_rows) > MAX_ROWS:
        raise ValidationError(f"Sheet export row limit exceeded: max {MAX_ROWS}.")

    selected_columns = [_validate_column_name(column) for column in (columns or _infer_columns(source_rows))]
    if not selected_columns:
        raise ValidationError("Sheet export requires at least one safe column.")
    if len(selected_columns) > MAX_COLUMNS:
        raise ValidationError(f"Sheet export column limit exceeded: max {MAX_COLUMNS}.")

    normalized_rows: list[list[Any]] = []
    for row in source_rows:
        if isinstance(row, dict):
            normalized_rows.append([_validate_cell(row.get(column, ""), column) for column in selected_columns])
        elif isinstance(row, list):
            if not columns:
                raise ValidationError("columns are required when rows are arrays.")
            normalized_rows.append([_validate_cell(row[index] if index < len(row) else "", selected_columns[index]) for index in range(len(selected_columns))])
        else:
            raise ValidationError("Each row must be an object or array.")
    return selected_columns, normalized_rows


def _safe_tab_name(value: str, idempotency_key: str) -> str:
    seed = str(value or idempotency_key or "analysis").strip()
    seed = re.sub(r"[\[\]\*\?/\\:]+", " ", seed)
    seed = re.sub(r"\s+", " ", seed).strip()
    if not seed:
        seed = "analysis"
    suffix = hashlib.sha1(str(idempotency_key or seed).encode("utf-8")).hexdigest()[:8]
    base = seed[: max(1, MAX_TAB_NAME_CHARS - 9)].strip()
    return f"{base}-{suffix}"[:MAX_TAB_NAME_CHARS]


def _stable_idempotency_key(analysis_type: str, title: str, source_permalink: str) -> str:
    material = "|".join([analysis_type.strip().lower(), title.strip().lower(), source_permalink.strip()])
    return hashlib.sha1(material.encode("utf-8")).hexdigest()[:16]


def _prepare_export(
    slack_user_email: str,
    analysis_type: str,
    title: str,
    columns: list[Any] | None,
    rows: list[Any] | None,
    idempotency_key: str,
    source_permalink: str,
    source_summary: str,
    sheet_tab_name: str,
    spreadsheet_id: str,
) -> dict[str, Any]:
    caller = str(slack_user_email or "").strip().lower()
    if not caller:
        raise ValidationError("slack_user_email is required.")
    analysis = str(analysis_type or "").strip()[:80]
    if not analysis:
        raise ValidationError("analysis_type is required.")
    safe_title = str(title or analysis).strip()[:MAX_TITLE_CHARS]
    selected_spreadsheet_id = _spreadsheet_id(spreadsheet_id)
    safe_columns, safe_rows = _normalize_table(columns, rows)
    safe_source_summary = str(source_summary or "").strip()
    if safe_source_summary:
        _validate_cell(safe_source_summary[:MAX_CELL_CHARS], "source_summary")
    key = str(idempotency_key or "").strip() or _stable_idempotency_key(analysis, safe_title, source_permalink)
    tab_name = _safe_tab_name(sheet_tab_name or safe_title or analysis, key)
    return {
        "spreadsheet_id": selected_spreadsheet_id,
        "spreadsheet_url": _spreadsheet_url(selected_spreadsheet_id),
        "analysis_type": analysis,
        "title": safe_title,
        "columns": safe_columns,
        "rows": safe_rows,
        "row_count": len(safe_rows),
        "column_count": len(safe_columns),
        "idempotency_key": key,
        "tab_name": tab_name,
        "source_permalink": str(source_permalink or "").strip()[:MAX_CELL_CHARS],
        "source_summary": safe_source_summary[:MAX_CELL_CHARS],
        "caller_email": caller,
    }


def _api_url(spreadsheet_id: str, suffix: str, params: dict[str, Any] | None = None) -> str:
    url = f"{GOOGLE_SHEETS_API_BASE_URL}/{urllib.parse.quote(spreadsheet_id)}{suffix}"
    query = urllib.parse.urlencode({key: value for key, value in (params or {}).items() if value not in (None, "")})
    return f"{url}?{query}" if query else url


def _sheets_request(
    method: str,
    spreadsheet_id: str,
    suffix: str,
    access_token: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        _api_url(spreadsheet_id, suffix, params),
        data=data,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": GOOGLE_SHEETS_USER_AGENT,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=GOOGLE_SHEETS_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise GoogleSheetsError(f"Google Sheets API failed: {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise GoogleSheetsError(f"Google Sheets API request timed out or failed: {reason}") from error


def _sheet_metadata(access_token: str, spreadsheet_id: str) -> dict[str, Any]:
    return _sheets_request(
        "GET",
        spreadsheet_id,
        "",
        access_token,
        params={"fields": "spreadsheetId,properties.title,sheets.properties(sheetId,title,index)"},
    )


def _sheet_id(metadata: dict[str, Any], title: str) -> int | None:
    for sheet in metadata.get("sheets", []) or []:
        props = sheet.get("properties", {})
        if props.get("title") == title:
            return int(props.get("sheetId"))
    return None


def _ensure_sheet(access_token: str, spreadsheet_id: str, metadata: dict[str, Any], title: str) -> tuple[int | None, bool]:
    existing = _sheet_id(metadata, title)
    if existing is not None:
        return existing, False
    response = _sheets_request(
        "POST",
        spreadsheet_id,
        ":batchUpdate",
        access_token,
        body={"requests": [{"addSheet": {"properties": {"title": title}}}]},
    )
    replies = response.get("replies", []) or []
    for reply in replies:
        props = reply.get("addSheet", {}).get("properties", {})
        if props.get("title") == title:
            return int(props.get("sheetId")), True
    return None, True


def _quote_range(tab_name: str, range_suffix: str) -> str:
    escaped = tab_name.replace("'", "''")
    return f"'{escaped}'!{range_suffix}"


def _column_letter(index: int) -> str:
    if index < 1:
        return "A"
    letters = ""
    current = index
    while current:
        current, remainder = divmod(current - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def _values_get(access_token: str, spreadsheet_id: str, range_name: str) -> list[list[Any]]:
    response = _sheets_request(
        "GET",
        spreadsheet_id,
        f"/values/{urllib.parse.quote(range_name, safe='')}",
        access_token,
        params={"majorDimension": "ROWS"},
    )
    return response.get("values", []) or []


def _values_update(access_token: str, spreadsheet_id: str, range_name: str, values: list[list[Any]]) -> None:
    _sheets_request(
        "PUT",
        spreadsheet_id,
        f"/values/{urllib.parse.quote(range_name, safe='')}",
        access_token,
        params={"valueInputOption": "RAW"},
        body={"values": values},
    )


def _values_clear(access_token: str, spreadsheet_id: str, range_name: str) -> None:
    _sheets_request("POST", spreadsheet_id, f"/values/{urllib.parse.quote(range_name, safe='')}:clear", access_token, body={})


def _upsert_runs_index(existing: list[list[Any]], record: list[Any]) -> tuple[list[list[Any]], str, int]:
    rows = existing or []
    if not rows:
        rows = [RUNS_HEADER]
    elif rows[0] != RUNS_HEADER:
        rows[0] = RUNS_HEADER
    target_key = str(record[0])
    for index, row in enumerate(rows[1:], start=2):
        if row and str(row[0]) == target_key:
            rows[index - 1] = record
            return rows, "updated", index
    rows.append(record)
    return rows, "created", len(rows)


def _apply_export(prepared: dict[str, Any]) -> dict[str, Any]:
    access_token = _access_token()
    spreadsheet_id = prepared["spreadsheet_id"]
    metadata = _sheet_metadata(access_token, spreadsheet_id)
    _ensure_sheet(access_token, spreadsheet_id, metadata, RUNS_TAB_NAME)
    metadata = _sheet_metadata(access_token, spreadsheet_id)
    run_sheet_id, created_tab = _ensure_sheet(access_token, spreadsheet_id, metadata, prepared["tab_name"])

    run_range = _quote_range(prepared["tab_name"], "A1:ZZ")
    _values_clear(access_token, spreadsheet_id, run_range)
    last_column = _column_letter(prepared["column_count"])
    _values_update(
        access_token,
        spreadsheet_id,
        _quote_range(prepared["tab_name"], f"A1:{last_column}{prepared['row_count'] + 1}"),
        [prepared["columns"], *prepared["rows"]],
    )

    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    record = [
        prepared["idempotency_key"],
        updated_at,
        prepared["analysis_type"],
        prepared["title"],
        prepared["tab_name"],
        prepared["source_permalink"],
        prepared["row_count"],
        prepared["caller_email"],
    ]
    existing_runs = _values_get(access_token, spreadsheet_id, _quote_range(RUNS_TAB_NAME, "A1:H"))
    runs_rows, index_action, index_row = _upsert_runs_index(existing_runs, record)
    _values_update(access_token, spreadsheet_id, _quote_range(RUNS_TAB_NAME, f"A1:H{len(runs_rows)}"), runs_rows)
    metadata = _sheet_metadata(access_token, spreadsheet_id)
    run_sheet_id = _sheet_id(metadata, prepared["tab_name"]) if run_sheet_id is None else run_sheet_id
    return {
        **prepared,
        "sheet_url": _sheet_url(spreadsheet_id, run_sheet_id),
        "runs_index_action": index_action,
        "runs_index_row": index_row,
        "created_run_tab": created_tab,
        "updated_at": updated_at,
    }


@mcp.tool()
def preview_analysis_sheet_export(
    slack_user_email: str,
    analysis_type: str,
    columns: list[Any] | None = None,
    rows: list[Any] | None = None,
    idempotency_key: str = "",
    title: str = "",
    source_permalink: str = "",
    source_summary: str = "",
    sheet_tab_name: str = "",
    spreadsheet_id: str = "",
) -> dict[str, Any]:
    """Validate a sanitized analysis table and preview the shared workbook write."""

    try:
        prepared = _prepare_export(
            slack_user_email,
            analysis_type,
            title,
            columns,
            rows,
            idempotency_key,
            source_permalink,
            source_summary,
            sheet_tab_name,
            spreadsheet_id,
        )
        return {
            "answer": {
                "will_mutate_google_sheets": False,
                "spreadsheet_url": prepared["spreadsheet_url"],
                "planned_tab_name": prepared["tab_name"],
                "runs_index_tab": RUNS_TAB_NAME,
                "idempotency_key": prepared["idempotency_key"],
                "row_count": prepared["row_count"],
                "column_count": prepared["column_count"],
                "columns": prepared["columns"],
                "planned_updates": [
                    "validate sanitized columns and rows",
                    "upsert Runs index row by idempotency_key",
                    "create or replace one run tab by idempotency_key",
                ],
            },
            "source": "Local Google Sheets export validator",
            "scope": {
                "caller_email": prepared["caller_email"],
                "analysis_type": prepared["analysis_type"],
                "account_email": _account_email(),
            },
            "confidence": "verified",
            "caveat": "Preview only. No Google Sheets API call or mutation was performed.",
        }
    except ValidationError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "analysis_type": analysis_type})


@mcp.tool()
def apply_analysis_sheet_export(
    slack_user_email: str,
    analysis_type: str,
    columns: list[Any] | None = None,
    rows: list[Any] | None = None,
    idempotency_key: str = "",
    title: str = "",
    source_permalink: str = "",
    source_summary: str = "",
    sheet_tab_name: str = "",
    spreadsheet_id: str = "",
) -> dict[str, Any]:
    """Write a sanitized analysis table to the shared workbook and upsert Runs."""

    try:
        prepared = _prepare_export(
            slack_user_email,
            analysis_type,
            title,
            columns,
            rows,
            idempotency_key,
            source_permalink,
            source_summary,
            sheet_tab_name,
            spreadsheet_id,
        )
        applied = _apply_export(prepared)
        return {
            "answer": {
                "will_mutate_google_sheets": True,
                "spreadsheet_url": applied["spreadsheet_url"],
                "sheet_url": applied["sheet_url"],
                "tab_name": applied["tab_name"],
                "runs_index_tab": RUNS_TAB_NAME,
                "runs_index_action": applied["runs_index_action"],
                "runs_index_row": applied["runs_index_row"],
                "created_run_tab": applied["created_run_tab"],
                "idempotency_key": applied["idempotency_key"],
                "row_count": applied["row_count"],
                "column_count": applied["column_count"],
                "updated_at": applied["updated_at"],
            },
            "source": "Google Sheets API",
            "scope": {
                "caller_email": applied["caller_email"],
                "analysis_type": applied["analysis_type"],
                "account_email": _account_email(),
            },
            "confidence": "verified",
            "caveat": "Sanitized analysis rows only. Raw Slack transcripts, phone numbers, full attendee emails, raw HubSpot bodies, and raw guest exports are rejected before write.",
        }
    except ValidationError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "analysis_type": analysis_type})
    except GoogleSheetsError as error:
        return _blocked(str(error), {"caller_email": slack_user_email, "analysis_type": analysis_type, "status_code": error.status_code})


if __name__ == "__main__":
    mcp.run()
