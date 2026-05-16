#!/usr/bin/env python3
"""Diagnose and repair NurtureAny Slack allowed-user drift.

This no-agent script treats the runtime access policy as the approved source of
access. It can update SLACK_ALLOWED_USERS to match already-approved policy
emails, but it does not grant new access-policy roles from Slack metadata.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROFILE_NAME = "nurtureanysalesbot"
ACCESS_POLICY_ENV_VAR = "NURTUREANY_ACCESS_POLICY_PATH"
BUILT_IN_ADMINS = {
    "eugene@staffany.com",
    "kaiyi@staffany.com",
    "kai.yi@staffany.com",
    "leekai.yi@staffany.com",
}
BUILT_IN_MANAGERS = {
    "kerren.fong@staffany.com",
    "sarah@staffany.com",
    "sarah.ayutania@staffany.com",
}


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
            value = _normalize_email(entry.get(key))
            if value:
                return value
    return ""


def read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def read_policy(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("access policy must be a JSON object")
    return data


def access_policy_emails(policy: dict[str, Any], include_built_ins: bool = True) -> list[str]:
    emails: list[str] = []
    disabled = {
        _entry_email(entry, "email", "slack_email", "hubspot_owner_email")
        for key in ("disabled", "unclassified")
        for entry in policy.get(key, [])
    }

    def add(email: str) -> None:
        normalized = _normalize_email(email)
        if normalized and normalized not in disabled and normalized not in emails:
            emails.append(normalized)

    if include_built_ins:
        for email in sorted(BUILT_IN_ADMINS | BUILT_IN_MANAGERS):
            add(email)

    for key in ("admins", "managers", "event_operators", "regional_event_operators"):
        for entry in policy.get(key, []):
            add(_entry_email(entry, "email", "slack_email"))

    for entry in policy.get("sales_reps", []):
        if not isinstance(entry, dict) or entry.get("active") is False:
            continue
        add(_normalize_email(entry.get("slack_email") or entry.get("email")))

    return sorted(emails)


def allowed_user_ids(raw_value: str) -> list[str]:
    return sorted({item.strip() for item in str(raw_value or "").split(",") if item.strip()})


def slack_lookup_by_email(token: str, email: str) -> dict[str, Any]:
    url = "https://slack.com/api/users.lookupByEmail?" + urllib.parse.urlencode({"email": email})
    request = urllib.request.Request(url, headers={"authorization": f"Bearer {token}"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not payload.get("ok"):
        return {"email": email, "ok": False, "error": payload.get("error") or "unknown_error"}
    user = payload.get("user") or {}
    return {
        "email": email,
        "ok": True,
        "user_id": str(user.get("id") or ""),
        "deleted": bool(user.get("deleted")),
        "is_bot": bool(user.get("is_bot")),
    }


def resolve_policy_users(token: str, emails: list[str]) -> tuple[list[str], list[dict[str, Any]]]:
    user_ids: list[str] = []
    lookups: list[dict[str, Any]] = []
    for email in emails:
        try:
            lookup = slack_lookup_by_email(token, email)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            lookup = {"email": email, "ok": False, "error": type(error).__name__}
        lookups.append(lookup)
        user_id = str(lookup.get("user_id") or "")
        if lookup.get("ok") and user_id and not lookup.get("deleted") and user_id not in user_ids:
            user_ids.append(user_id)
    return sorted(user_ids), lookups


def update_dotenv_allowed_users(path: Path, user_ids: list[str]) -> Path:
    existing = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    updated: list[str] = []
    replaced = False
    value = ",".join(user_ids)
    for line in existing:
        if line.startswith("SLACK_ALLOWED_USERS="):
            updated.append(f"SLACK_ALLOWED_USERS={value}")
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        updated.append(f"SLACK_ALLOWED_USERS={value}")

    backup = path.with_suffix(path.suffix + f".bak.{time.strftime('%Y%m%d%H%M%S')}")
    if path.exists():
        backup.write_text("\n".join(existing) + ("\n" if existing else ""), encoding="utf-8")
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")
    try:
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
    except PermissionError:
        pass
    return backup


def restart_gateway(service_name: str) -> dict[str, Any]:
    command = ["systemctl", "--user", "restart", service_name]
    result = subprocess.run(command, text=True, capture_output=True, check=False)
    return {
        "command": " ".join(command),
        "returncode": result.returncode,
        "stderr": result.stderr.strip()[:300],
    }


def run_health_check(path: str) -> dict[str, Any]:
    if not path:
        return {"skipped": True}
    result = subprocess.run([path], text=True, capture_output=True, check=False)
    return {
        "command": path,
        "returncode": result.returncode,
        "stdout": result.stdout.strip()[:500],
        "stderr": result.stderr.strip()[:500],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync NurtureAny SLACK_ALLOWED_USERS from the approved runtime policy.")
    parser.add_argument("--profile-env", default=str(Path.home() / ".hermes" / "profiles" / PROFILE_NAME / ".env"))
    parser.add_argument("--access-policy", default="")
    parser.add_argument("--apply", action="store_true", help="Update .env, restart gateway, and optionally run health check.")
    parser.add_argument("--no-restart", action="store_true", help="Do not restart the gateway after --apply.")
    parser.add_argument("--service-name", default="hermes-gateway-nurtureanysalesbot.service")
    parser.add_argument("--health-check", default="")
    parser.add_argument("--expect-email", action="append", default=[], help="Report whether a specific email is policy-approved and resolved.")
    args = parser.parse_args()

    profile_env_path = Path(args.profile_env).expanduser()
    profile_env = read_dotenv(profile_env_path)
    merged_env = {**profile_env, **os.environ}
    policy_path_text = args.access_policy or merged_env.get(ACCESS_POLICY_ENV_VAR, "")
    if not policy_path_text:
        print(json.dumps({"ok": False, "error": "access-policy-path-missing"}, sort_keys=True))
        return 2
    policy_path = Path(policy_path_text).expanduser()
    if not policy_path.exists():
        print(json.dumps({"ok": False, "error": "access-policy-not-found", "path": str(policy_path)}, sort_keys=True))
        return 2
    token = merged_env.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        print(json.dumps({"ok": False, "error": "slack-bot-token-missing"}, sort_keys=True))
        return 2

    policy = read_policy(policy_path)
    expected_emails = access_policy_emails(policy)
    expected_user_ids, lookups = resolve_policy_users(token, expected_emails)
    current_user_ids = allowed_user_ids(merged_env.get("SLACK_ALLOWED_USERS", ""))
    missing = sorted(set(expected_user_ids) - set(current_user_ids))
    extra = sorted(set(current_user_ids) - set(expected_user_ids))
    expect_email_reports = []
    lookup_by_email = {item["email"]: item for item in lookups}
    for email in args.expect_email:
        normalized = _normalize_email(email)
        expect_email_reports.append(
            {
                "email": normalized,
                "policy_approved": normalized in expected_emails,
                "slack_lookup": lookup_by_email.get(normalized, {"ok": False, "error": "not_in_policy_email_set"}),
            }
        )

    result: dict[str, Any] = {
        "ok": not missing and not extra,
        "mode": "apply" if args.apply else "dry_run",
        "profile_env": str(profile_env_path),
        "access_policy": str(policy_path),
        "policy_email_count": len(expected_emails),
        "resolved_policy_user_count": len(expected_user_ids),
        "current_allowed_user_count": len(current_user_ids),
        "missing_user_ids": missing,
        "extra_user_ids": extra,
        "lookup_errors": [item for item in lookups if not item.get("ok")],
        "expect_email": expect_email_reports,
    }

    if args.apply:
        backup = update_dotenv_allowed_users(profile_env_path, expected_user_ids)
        result["updated_env_backup"] = str(backup)
        if args.no_restart:
            result["restart"] = {"skipped": True}
        else:
            result["restart"] = restart_gateway(args.service_name)
        result["health_check"] = run_health_check(args.health_check)
        result["ok"] = not result.get("restart", {}).get("returncode") and result.get("health_check", {}).get("returncode", 0) == 0

    print(json.dumps(result, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
