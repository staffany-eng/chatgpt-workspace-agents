#!/usr/bin/env python3
"""Creation-only Google Sheets output MCP for StaffAny Hermes bots."""

from __future__ import annotations

import json
import os
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from mcp.server.fastmcp import FastMCP

from google_oauth import (
    access_token as _google_access_token,
    account_email as _google_account_email,
    load_profile_env,
    profile_file as _google_profile_file,
    safe_detail as _safe_detail,
)


load_profile_env()

DEFAULT_ACCOUNT_EMAIL = "team@staffany.com"
GOOGLE_SHEETS_ACCOUNT_ENV = "GOOGLE_SHEETS_ACCOUNT_EMAIL"
GOOGLE_SHEETS_TOKEN_FILE_ENV = "GOOGLE_SHEETS_TOKEN_FILE"
GOOGLE_SHEETS_CLIENT_SECRET_FILE_ENV = "GOOGLE_SHEETS_CLIENT_SECRET_FILE"
GOOGLE_SHEETS_OUTPUT_FOLDER_ID_ENV = "GOOGLE_SHEETS_OUTPUT_FOLDER_ID"
GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS_ENV = "GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS"
GOOGLE_SHEETS_OUTPUT_SHARE_ROLE_ENV = "GOOGLE_SHEETS_OUTPUT_SHARE_ROLE"
GOOGLE_SHEETS_API_BASE_URL = "https://sheets.googleapis.com/v4/spreadsheets"
GOOGLE_DRIVE_API_BASE_URL = "https://www.googleapis.com/drive/v3"
SPREADSHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
REQUIRED_SCOPES = {SPREADSHEETS_SCOPE, DRIVE_FILE_SCOPE}
USER_AGENT = "StaffAny-GoogleSheetsOutput/1.0 (+https://staffany.com)"
TIMEOUT_SECONDS = 20
MAX_TABS = 5
MAX_ROWS_PER_TAB = 5000
MAX_TOTAL_CELLS = 100_000
MAX_CELL_CHARS = 2000
MAX_TITLE_CHARS = 120
MAX_TAB_NAME_CHARS = 80
FORMULA_PREFIXES = ("=", "+", "-", "@")
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

mcp = FastMCP(
    "staffany_google_sheets",
    instructions=(
        "Creation-only Google Sheets output for StaffAny Hermes bots. Use the "
        "team@staffany.com OAuth account, create bounded spreadsheets from approved "
        "table output, escape formula-like cells, and never edit existing Sheets."
    ),
)


class StaffAnyGoogleSheetsError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _account_email() -> str:
    return _google_account_email(GOOGLE_SHEETS_ACCOUNT_ENV, DEFAULT_ACCOUNT_EMAIL)


def _token_file():
    return _google_profile_file(GOOGLE_SHEETS_TOKEN_FILE_ENV, "google-sheets-token.json")


def _client_secret_file():
    return _google_profile_file(GOOGLE_SHEETS_CLIENT_SECRET_FILE_ENV, "google-sheets-client-secret.json")


def _scope(slack_user_email: str = "", extra: dict[str, Any] | None = None) -> dict[str, Any]:
    scope = {
        "caller_email": str(slack_user_email or "").strip().lower(),
        "google_account_email": _account_email(),
        "access_mode": "team_oauth_google_sheets_output",
        "service_account": False,
        "read_existing_spreadsheets": False,
        "edit_existing_spreadsheets": False,
        "create_only": True,
        "required_scopes": sorted(REQUIRED_SCOPES),
    }
    if extra:
        scope.update(extra)
    return scope


def _blocked(message: str, scope: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "answer": message,
        "source": "staffany_google_sheets",
        "scope": scope or _scope(),
        "confidence": "blocked",
        "caveat": "No token values, OAuth file content, existing Sheet edits, or user-token fallback were used.",
    }


def _configured_share_emails() -> list[str]:
    raw = os.environ.get(GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS_ENV, "").strip()
    if not raw or (raw.startswith("${") and raw.endswith("}")):
        return []
    emails = []
    for item in raw.split(","):
        email = item.strip().lower()
        if email:
            emails.append(email)
    return emails


def _configured_folder_id() -> str:
    value = os.environ.get(GOOGLE_SHEETS_OUTPUT_FOLDER_ID_ENV, "").strip()
    if value.startswith("${") and value.endswith("}"):
        return ""
    return value


def _share_role() -> str:
    role = os.environ.get(GOOGLE_SHEETS_OUTPUT_SHARE_ROLE_ENV, "reader").strip().lower()
    return role if role in {"reader", "writer"} else "reader"


def _validate_access_policy(scope: dict[str, Any]) -> tuple[str, list[str], str] | dict[str, Any]:
    folder_id = _configured_folder_id()
    share_emails = _configured_share_emails()
    invalid_emails = [email for email in share_emails if not EMAIL_PATTERN.match(email)]
    if invalid_emails:
        return _blocked("GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS contains invalid email values.", {**scope, "invalid_share_emails": invalid_emails})
    if not folder_id and not share_emails:
        return _blocked(
            f"Missing {GOOGLE_SHEETS_OUTPUT_FOLDER_ID_ENV} or {GOOGLE_SHEETS_OUTPUT_SHARE_EMAILS_ENV}; refusing to create an inaccessible Sheet.",
            scope,
        )
    return folder_id, share_emails, _share_role()


def _access_token() -> str:
    return _google_access_token(
        _token_file(),
        _client_secret_file(),
        REQUIRED_SCOPES,
        USER_AGENT,
        TIMEOUT_SECONDS,
        "Google Sheets output",
        StaffAnyGoogleSheetsError,
    )


def _safe_error(message: str) -> str:
    token = os.environ.get("GOOGLE_SHEETS_TOKEN", "").strip()
    safe = str(message).replace(token, "[REDACTED_GOOGLE_SHEETS_TOKEN]") if token else str(message)
    return _safe_detail(safe, 500)


def _request_json(
    method: str,
    url: str,
    access_token: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if params:
        query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
        if query:
            url = f"{url}?{query}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "content-type": "application/json",
            "user-agent": USER_AGENT,
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise StaffAnyGoogleSheetsError(f"Google API failed: HTTP {error.code} {_safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise StaffAnyGoogleSheetsError(f"Google API request failed: {reason}") from error
    except json.JSONDecodeError as error:
        raise StaffAnyGoogleSheetsError("Google API returned invalid JSON.") from error


def _clean_title(value: str, fallback: str) -> str:
    title = " ".join(str(value or "").split())[:MAX_TITLE_CHARS].strip()
    return title or fallback


def _clean_tab_name(value: str, index: int) -> str:
    name = " ".join(str(value or "").split()).strip() or f"Sheet {index + 1}"
    for char in "[]:*?/\\'":
        name = name.replace(char, " ")
    name = " ".join(name.split())[:MAX_TAB_NAME_CHARS].strip()
    return name or f"Sheet {index + 1}"


def _escape_cell(value: Any) -> str | int | float | bool:
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        return value
    text = str(value)
    if len(text) > MAX_CELL_CHARS:
        text = text[:MAX_CELL_CHARS]
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def _normalize_rows(rows: Any) -> list[list[Any]]:
    if not isinstance(rows, list):
        raise StaffAnyGoogleSheetsError("Each tab rows value must be a list.")
    normalized: list[list[Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append([_escape_cell(value) for value in row.values()])
        elif isinstance(row, list):
            normalized.append([_escape_cell(value) for value in row])
        else:
            normalized.append([_escape_cell(row)])
    return normalized


def _normalize_tabs(tabs: Any) -> tuple[list[dict[str, Any]], int, int]:
    if not isinstance(tabs, list) or not tabs:
        raise StaffAnyGoogleSheetsError("tabs must be a non-empty list.")
    if len(tabs) > MAX_TABS:
        raise StaffAnyGoogleSheetsError(f"Too many tabs requested; max is {MAX_TABS}.")

    normalized_tabs: list[dict[str, Any]] = []
    total_rows = 0
    total_cells = 0
    seen_names: set[str] = set()
    for index, raw_tab in enumerate(tabs):
        if not isinstance(raw_tab, dict):
            raise StaffAnyGoogleSheetsError("Each tab must be an object with name and rows.")
        name = _clean_tab_name(str(raw_tab.get("name") or ""), index)
        base_name = name
        suffix = 2
        while name.lower() in seen_names:
            name = f"{base_name[:MAX_TAB_NAME_CHARS - 4]} {suffix}".strip()
            suffix += 1
        seen_names.add(name.lower())

        rows = _normalize_rows(raw_tab.get("rows"))
        if len(rows) > MAX_ROWS_PER_TAB:
            raise StaffAnyGoogleSheetsError(f"Tab {name} has too many rows; max is {MAX_ROWS_PER_TAB}.")
        cells = sum(len(row) for row in rows)
        total_rows += len(rows)
        total_cells += cells
        normalized_tabs.append({"name": name, "rows": rows})

    if total_cells > MAX_TOTAL_CELLS:
        raise StaffAnyGoogleSheetsError(f"Too many cells requested; max is {MAX_TOTAL_CELLS}.")
    return normalized_tabs, total_rows, total_cells


def _create_spreadsheet(title: str, tabs: list[dict[str, Any]], access_token: str) -> dict[str, Any]:
    payload = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": tab["name"]}} for tab in tabs],
    }
    return _request_json("POST", GOOGLE_SHEETS_API_BASE_URL, access_token, payload=payload)


def _write_values(spreadsheet_id: str, tabs: list[dict[str, Any]], access_token: str) -> None:
    data = [
        {
            "range": f"'{tab['name']}'!A1",
            "majorDimension": "ROWS",
            "values": tab["rows"],
        }
        for tab in tabs
        if tab["rows"]
    ]
    if not data:
        return
    url = f"{GOOGLE_SHEETS_API_BASE_URL}/{urllib.parse.quote(spreadsheet_id, safe='')}/values:batchUpdate"
    _request_json("POST", url, access_token, payload={"valueInputOption": "RAW", "data": data})


def _move_to_folder(spreadsheet_id: str, folder_id: str, access_token: str) -> bool:
    if not folder_id:
        return False
    url = f"{GOOGLE_DRIVE_API_BASE_URL}/files/{urllib.parse.quote(spreadsheet_id, safe='')}"
    _request_json(
        "PATCH",
        url,
        access_token,
        params={"addParents": folder_id, "fields": "id,parents", "supportsAllDrives": "true"},
    )
    return True


def _share_file(spreadsheet_id: str, emails: list[str], role: str, access_token: str) -> list[str]:
    shared: list[str] = []
    for email in emails:
        url = f"{GOOGLE_DRIVE_API_BASE_URL}/files/{urllib.parse.quote(spreadsheet_id, safe='')}/permissions"
        _request_json(
            "POST",
            url,
            access_token,
            payload={"type": "user", "role": role, "emailAddress": email},
            params={"sendNotificationEmail": "false", "supportsAllDrives": "true"},
        )
        shared.append(email)
    return shared


@mcp.tool()
def check_google_sheets_output_access(slack_user_email: str = "", account_email: str = DEFAULT_ACCOUNT_EMAIL) -> dict[str, Any]:
    """Check whether creation-only Google Sheets output is configured."""

    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    configured_account = _account_email()
    scope = _scope(slack_user_email, {"requested_account_email": requested_account})
    if requested_account != configured_account:
        return _blocked("Google Sheets output is restricted to team@staffany.com.", scope)
    policy = _validate_access_policy(scope)
    if isinstance(policy, dict):
        return policy
    folder_id, share_emails, share_role = policy
    try:
        _access_token()
    except StaffAnyGoogleSheetsError as error:
        return _blocked(_safe_error(str(error)), scope)

    return {
        "answer": {
            "ready": True,
            "account_email": configured_account,
            "output_folder_configured": bool(folder_id),
            "share_target_count": len(share_emails),
            "share_role": share_role if share_emails else "",
            "allowed_tools": ["check_google_sheets_output_access", "create_spreadsheet_from_rows"],
            "limits": {
                "max_tabs": MAX_TABS,
                "max_rows_per_tab": MAX_ROWS_PER_TAB,
                "max_total_cells": MAX_TOTAL_CELLS,
                "max_cell_chars": MAX_CELL_CHARS,
            },
        },
        "source": "Google Sheets OAuth config and output policy",
        "scope": {**scope, "output_folder_configured": bool(folder_id), "share_target_count": len(share_emails)},
        "confidence": "verified",
        "caveat": "This only verifies connector configuration; it does not create a spreadsheet.",
    }


@mcp.tool()
def create_spreadsheet_from_rows(
    slack_user_email: str,
    title: str,
    tabs: list[dict[str, Any]],
    source: str = "",
    scope_note: str = "",
    account_email: str = DEFAULT_ACCOUNT_EMAIL,
) -> dict[str, Any]:
    """Create a new Google Sheet from bounded structured row data."""

    requested_account = (account_email or DEFAULT_ACCOUNT_EMAIL).strip().lower()
    configured_account = _account_email()
    base_scope = _scope(
        slack_user_email,
        {
            "requested_account_email": requested_account,
            "source": source,
            "scope_note": scope_note,
            "limits": {
                "max_tabs": MAX_TABS,
                "max_rows_per_tab": MAX_ROWS_PER_TAB,
                "max_total_cells": MAX_TOTAL_CELLS,
                "max_cell_chars": MAX_CELL_CHARS,
            },
        },
    )
    if requested_account != configured_account:
        return _blocked("Google Sheets output is restricted to team@staffany.com.", base_scope)

    policy = _validate_access_policy(base_scope)
    if isinstance(policy, dict):
        return policy
    folder_id, share_emails, share_role = policy

    try:
        normalized_tabs, total_rows, total_cells = _normalize_tabs(tabs)
    except StaffAnyGoogleSheetsError as error:
        return _blocked(str(error), base_scope)

    spreadsheet_title = _clean_title(title, "StaffAny Bot Output")
    try:
        token = _access_token()
        spreadsheet = _create_spreadsheet(spreadsheet_title, normalized_tabs, token)
        spreadsheet_id = str(spreadsheet.get("spreadsheetId") or "").strip()
        spreadsheet_url = str(spreadsheet.get("spreadsheetUrl") or "").strip()
        if not spreadsheet_id:
            return _blocked("Google Sheets API did not return a spreadsheet id.", base_scope)
        _write_values(spreadsheet_id, normalized_tabs, token)
        moved_to_folder = _move_to_folder(spreadsheet_id, folder_id, token)
        shared_with = _share_file(spreadsheet_id, share_emails, share_role, token)
    except StaffAnyGoogleSheetsError as error:
        return _blocked(_safe_error(str(error)), base_scope)

    return {
        "answer": {
            "spreadsheet_title": spreadsheet_title,
            "spreadsheet_id": spreadsheet_id,
            "spreadsheet_url": spreadsheet_url or f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit",
            "tab_count": len(normalized_tabs),
            "row_count": total_rows,
            "cell_count": total_cells,
            "tabs": [{"name": tab["name"], "row_count": len(tab["rows"])} for tab in normalized_tabs],
            "moved_to_output_folder": moved_to_folder,
            "shared_target_count": len(shared_with),
            "share_role": share_role if shared_with else "",
            "formula_like_cells_escaped": True,
        },
        "source": f"{source} + staffany_google_sheets.create_spreadsheet_from_rows" if source else "staffany_google_sheets.create_spreadsheet_from_rows",
        "scope": {
            **base_scope,
            "tab_count": len(normalized_tabs),
            "row_count": total_rows,
            "cell_count": total_cells,
            "output_folder_configured": bool(folder_id),
            "share_target_count": len(shared_with),
        },
        "confidence": "verified",
        "caveat": "Creation-only Google Sheets output. Source system truth remains with the underlying query/tool result.",
    }


if __name__ == "__main__":
    mcp.run("stdio")
