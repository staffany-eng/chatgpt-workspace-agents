#!/usr/bin/env python3
"""Restricted BigQuery writer for approved NurtureAny near-me outlet matches.

The read-only near_me_nurtureany MCP prepares Slack review candidates. This job
is the separate write path: it accepts only Slack-approved, account-linked,
confirmed rows and emits or executes a bounded MERGE into the outlet-match table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ACCESS_POLICY_ENV_VAR = "NURTUREANY_ACCESS_POLICY_PATH"
OUTLET_MATCHES_TABLE_ENV = "NURTUREANY_OUTLET_MATCHES_TABLE"
DEFAULT_OUTLET_MATCHES_TABLE = "staffany-warehouse.analytics.nurtureany_near_me_outlet_matches"
SUPPORTED_COUNTRIES = ("Singapore", "Malaysia", "Indonesia")
OVERALL_ADMINS = {"eugene@staffany.com", "kaiyi@staffany.com", "kai.yi@staffany.com"}
REGIONAL_MANAGERS = {
    "kerren.fong@staffany.com": ("Singapore", "Malaysia"),
    "sarah@staffany.com": ("Indonesia",),
}
AREA_NAMES = {
    "sg_raffles_place": "Raffles Place",
    "sg_chinatown": "Chinatown / Telok Ayer",
    "sg_bugis_junction": "Bugis Junction",
    "sg_suntec_city": "Suntec City",
    "sg_tanjong_pagar": "Tanjong Pagar / Shenton",
    "sg_ion_orchard": "ION Orchard",
    "sg_boat_quay_clarke_quay": "Boat Quay / Clarke Quay",
    "sg_marina_bay": "Marina Bay / MBFC",
    "sg_westgate_jem": "Westgate / JEM",
    "sg_tampines_mall": "Tampines Mall",
    "sg_plaza_singapura": "Plaza Singapura",
    "sg_paya_lebar_quarter": "Paya Lebar Quarter",
    "sg_vivocity": "VivoCity",
    "sg_northpoint_yishun": "Northpoint City / Yishun",
    "sg_jewel_changi": "Jewel Changi Airport",
    "sg_nex": "NEX",
    "sg_jurong_point": "Jurong Point",
    "sg_causeway_point": "Causeway Point",
}
ACCOUNT_STATUSES = {"customer", "prospect"}
CONFIDENCES = {"verified", "needs-check"}
SOURCES = {"manual", "google_places", "import", "workflow"}
MERGE_COLUMNS = [
    "outlet_match_id",
    "area_id",
    "area_name",
    "outlet_name",
    "google_place_id",
    "formatted_address",
    "latitude",
    "longitude",
    "google_maps_uri",
    "hubspot_company_id",
    "hubspot_company_name",
    "hubspot_owner_id",
    "organisation_id",
    "account_status",
    "match_status",
    "confidence",
    "source",
    "source_note",
    "last_checked_at",
    "reviewed_by",
    "created_at",
    "updated_at",
]


class ValidationError(ValueError):
    pass


def _normalize_email(value: Any) -> str:
    return str(value or "").strip().lower()


def _string_list(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _entry_email(entry: Any, *keys: str) -> str:
    if isinstance(entry, str):
        return _normalize_email(entry)
    if isinstance(entry, dict):
        for key in keys:
            email = _normalize_email(entry.get(key))
            if email:
                return email
    return ""


def _normalize_countries(countries: list[str]) -> tuple[str, ...]:
    selected = []
    for country in countries or list(SUPPORTED_COUNTRIES):
        if country in SUPPORTED_COUNTRIES and country not in selected:
            selected.append(country)
    return tuple(selected)


def _load_access_policy_file() -> dict[str, Any]:
    path = os.environ.get(ACCESS_POLICY_ENV_VAR, "").strip()
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as error:
        raise ValidationError(f"{ACCESS_POLICY_ENV_VAR} file not found: {path}") from error
    except json.JSONDecodeError as error:
        raise ValidationError(f"{ACCESS_POLICY_ENV_VAR} is invalid JSON: {error}") from error
    if not isinstance(payload, dict):
        raise ValidationError(f"{ACCESS_POLICY_ENV_VAR} must point to a JSON object.")
    return payload


def _access_policy() -> dict[str, Any]:
    raw = _load_access_policy_file()
    admins = set(OVERALL_ADMINS)
    managers = dict(REGIONAL_MANAGERS)
    disabled: set[str] = set()

    for entry in raw.get("admins", []):
        email = _entry_email(entry, "email", "slack_email")
        if email:
            admins.add(email)

    for entry in raw.get("managers", []):
        email = _entry_email(entry, "email", "slack_email")
        if not email:
            continue
        countries = entry.get("countries") if isinstance(entry, dict) else None
        managers[email] = _normalize_countries(_string_list(countries))

    for key in ("disabled", "unclassified"):
        for entry in raw.get(key, []):
            email = _entry_email(entry, "email", "slack_email", "hubspot_owner_email")
            if email:
                disabled.add(email)

    return {
        "admins": admins - disabled,
        "managers": {email: countries for email, countries in managers.items() if email not in disabled},
        "disabled": disabled,
    }


def _reviewer_scope(email: str) -> dict[str, Any]:
    normalized = _normalize_email(email)
    policy = _access_policy()
    if not normalized or normalized in policy["disabled"]:
        return {"kind": "blocked", "email": normalized, "countries": ()}
    if normalized in policy["admins"]:
        return {"kind": "admin", "email": normalized, "countries": SUPPORTED_COUNTRIES}
    if normalized in policy["managers"] and "Singapore" in policy["managers"][normalized]:
        return {"kind": "manager", "email": normalized, "countries": policy["managers"][normalized]}
    return {"kind": "blocked", "email": normalized, "countries": ()}


def _clean_text(value: Any, maximum: int = 500) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    return text[:maximum]


def _clean_enum(value: Any, allowed: set[str], field: str) -> str:
    text = _clean_text(value).lower()
    if text not in allowed and text.replace("_", "-") in allowed:
        text = text.replace("_", "-")
    if text not in allowed:
        raise ValidationError(f"{field} must be one of {sorted(allowed)}.")
    return text


def _clean_float(value: Any, field: str, minimum: float, maximum: float) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as error:
        raise ValidationError(f"{field} must be numeric.") from error
    if not minimum <= parsed <= maximum:
        raise ValidationError(f"{field} is outside valid range.")
    return parsed


def _outlet_matches_table() -> str:
    table = os.environ.get(OUTLET_MATCHES_TABLE_ENV, "").strip() or DEFAULT_OUTLET_MATCHES_TABLE
    if not re.fullmatch(r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+", table):
        raise ValidationError(f"Invalid {OUTLET_MATCHES_TABLE_ENV}; expected project.dataset.table.")
    return table


def _stable_outlet_match_id(row: dict[str, Any]) -> str:
    existing = _clean_text(row.get("outlet_match_id"), 120)
    if existing:
        return existing
    raw = "|".join(
        [
            row["area_id"],
            row.get("google_place_id") or "",
            row.get("hubspot_company_id") or "",
            row.get("organisation_id") or "",
            row["outlet_name"].lower(),
        ]
    )
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]
    return f"nearme_{digest}"


def _validated_row(raw: dict[str, Any], reviewer_email: str, approval_marker: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationError("Every match row must be a JSON object.")
    area_id = _clean_text(raw.get("area_id"), 80)
    if area_id not in AREA_NAMES:
        raise ValidationError(f"Unknown area_id: {area_id}")
    outlet_name = _clean_text(raw.get("outlet_name") or raw.get("name"), 240)
    if not outlet_name:
        raise ValidationError("outlet_name is required.")
    hubspot_company_id = _clean_text(raw.get("hubspot_company_id") or raw.get("company_id"), 80)
    organisation_id = _clean_text(raw.get("organisation_id") or raw.get("organisationid"), 80)
    if not hubspot_company_id and not organisation_id:
        raise ValidationError("Approved rows must link to a HubSpot company or StaffAny organisation.")
    account_status = _clean_enum(raw.get("account_status"), ACCOUNT_STATUSES, "account_status")
    match_status = _clean_text(raw.get("match_status")).lower()
    if match_status != "confirmed":
        raise ValidationError("match_status must be confirmed for writer input.")

    row = {
        "area_id": area_id,
        "area_name": _clean_text(raw.get("area_name") or AREA_NAMES[area_id], 160),
        "outlet_name": outlet_name,
        "google_place_id": _clean_text(raw.get("google_place_id"), 180),
        "formatted_address": _clean_text(raw.get("formatted_address") or raw.get("address"), 500),
        "latitude": _clean_float(raw.get("latitude"), "latitude", -90, 90),
        "longitude": _clean_float(raw.get("longitude"), "longitude", -180, 180),
        "google_maps_uri": _clean_text(raw.get("google_maps_uri"), 500),
        "hubspot_company_id": hubspot_company_id,
        "hubspot_company_name": _clean_text(raw.get("hubspot_company_name") or raw.get("company_name"), 240),
        "hubspot_owner_id": _clean_text(raw.get("hubspot_owner_id"), 80),
        "organisation_id": organisation_id,
        "account_status": account_status,
        "match_status": "confirmed",
        "confidence": _clean_enum(raw.get("confidence") or "verified", CONFIDENCES, "confidence"),
        "source": _clean_enum(raw.get("source") or "workflow", SOURCES, "source"),
        "source_note": _clean_text(
            raw.get("source_note") or f"Slack-approved near-me seed; marker={approval_marker}",
            500,
        ),
        "reviewed_by": reviewer_email,
    }
    row["outlet_match_id"] = _stable_outlet_match_id(row)
    return row


def validate_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValidationError("Payload must be a JSON object.")
    reviewer_email = _normalize_email(payload.get("approved_by_email") or payload.get("reviewed_by"))
    reviewer = _reviewer_scope(reviewer_email)
    if reviewer["kind"] not in {"admin", "manager"}:
        raise ValidationError("approved_by_email must be a configured admin or Singapore-scoped manager.")
    approval_marker = _clean_text(payload.get("approval_marker"), 160)
    if not approval_marker:
        raise ValidationError("approval_marker is required.")
    matches = payload.get("matches")
    if not isinstance(matches, list) or not matches:
        raise ValidationError("matches must be a non-empty list.")
    return [_validated_row(row, reviewer_email, approval_marker) for row in matches]


def _sql_string(value: Any) -> str:
    if value in (None, ""):
        return "CAST(NULL AS STRING)"
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _sql_float(value: float | None) -> str:
    if value is None:
        return "CAST(NULL AS FLOAT64)"
    return repr(float(value))


def _source_select(row: dict[str, Any]) -> str:
    return f"""SELECT
  {_sql_string(row['outlet_match_id'])} AS outlet_match_id,
  {_sql_string(row['area_id'])} AS area_id,
  {_sql_string(row['area_name'])} AS area_name,
  {_sql_string(row['outlet_name'])} AS outlet_name,
  {_sql_string(row['google_place_id'])} AS google_place_id,
  {_sql_string(row['formatted_address'])} AS formatted_address,
  {_sql_float(row['latitude'])} AS latitude,
  {_sql_float(row['longitude'])} AS longitude,
  {_sql_string(row['google_maps_uri'])} AS google_maps_uri,
  {_sql_string(row['hubspot_company_id'])} AS hubspot_company_id,
  {_sql_string(row['hubspot_company_name'])} AS hubspot_company_name,
  {_sql_string(row['hubspot_owner_id'])} AS hubspot_owner_id,
  {_sql_string(row['organisation_id'])} AS organisation_id,
  {_sql_string(row['account_status'])} AS account_status,
  'confirmed' AS match_status,
  {_sql_string(row['confidence'])} AS confidence,
  {_sql_string(row['source'])} AS source,
  {_sql_string(row['source_note'])} AS source_note,
  CURRENT_TIMESTAMP() AS last_checked_at,
  {_sql_string(row['reviewed_by'])} AS reviewed_by,
  CURRENT_TIMESTAMP() AS created_at,
  CURRENT_TIMESTAMP() AS updated_at"""


def build_merge_sql(rows: list[dict[str, Any]], table: str | None = None) -> str:
    if not rows:
        raise ValidationError("At least one validated row is required.")
    destination = table or _outlet_matches_table()
    source_sql = "\nUNION ALL\n".join(_source_select(row) for row in rows)
    update_columns = [
        column
        for column in MERGE_COLUMNS
        if column not in {"outlet_match_id", "created_at"}
    ]
    update_sql = ",\n  ".join(f"{column} = S.{column}" for column in update_columns)
    insert_columns = ", ".join(MERGE_COLUMNS)
    insert_values = ", ".join(f"S.{column}" for column in MERGE_COLUMNS)
    return f"""-- NurtureAny near-me approved outlet-match writer.
-- Source: Slack-approved manager/admin review; No Google-only rows accepted.
MERGE `{destination}` T
USING (
{source_sql}
) S
ON T.outlet_match_id = S.outlet_match_id
WHEN MATCHED THEN UPDATE SET
  {update_sql}
WHEN NOT MATCHED THEN INSERT ({insert_columns})
VALUES ({insert_values});"""


def _load_payload(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValidationError("Input file must contain a JSON object.")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="JSON payload with approved_by_email, approval_marker, and matches.")
    parser.add_argument("--project-id", default=os.environ.get("GOOGLE_CLOUD_PROJECT", "gws-cli-260305163132"))
    parser.add_argument("--bq-bin", default=os.environ.get("BQ_BIN", "bq"))
    parser.add_argument("--execute", action="store_true", help="Run the MERGE through bq. Default prints SQL only.")
    parser.add_argument("--dry-run-bq", action="store_true", help="Ask bq to dry-run the generated MERGE.")
    args = parser.parse_args(argv)

    try:
        payload = _load_payload(args.input)
        rows = validate_payload(payload)
        sql = build_merge_sql(rows)
    except (OSError, json.JSONDecodeError, ValidationError) as error:
        print(f"blocked: {error}", file=sys.stderr)
        return 2

    if not args.execute and not args.dry_run_bq:
        print(sql)
        return 0

    command = [
        args.bq_bin,
        f"--project_id={args.project_id}",
        "query",
        "--use_legacy_sql=false",
    ]
    if args.dry_run_bq:
        command.append("--dry_run")
    completed = subprocess.run(command, input=sql, text=True, check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
