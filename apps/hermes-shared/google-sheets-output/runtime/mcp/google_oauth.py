"""Shared Google OAuth helpers for StaffAny Hermes Google adapters."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#") or "=" not in stripped:
        return None
    if stripped.startswith("export "):
        stripped = stripped[len("export ") :].strip()
    key, value = stripped.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def load_profile_env(default_profile_name: str = "staffanydatabot") -> None:
    """Load profile .env when Hermes starts MCP children with a filtered env."""

    explicit_paths = [
        os.environ.get("STAFFANY_GOOGLE_SHEETS_PROFILE_ENV", "").strip(),
        os.environ.get("STAFFANY_DATA_BOT_PROFILE_ENV", "").strip(),
        os.environ.get("HERMES_PROFILE_ENV", "").strip(),
    ]
    hermes_home = os.environ.get("HERMES_HOME", "").strip()
    profile_name = os.environ.get("HERMES_PROFILE", "").strip() or default_profile_name
    candidates = [Path(path) for path in explicit_paths if path]
    if hermes_home:
        candidates.append(Path(hermes_home) / ".env")
    candidates.append(Path.home() / ".hermes" / "profiles" / profile_name / ".env")

    seen: set[Path] = set()
    for candidate in candidates:
        path = candidate.expanduser()
        if path in seen or not path.exists():
            continue
        seen.add(path)
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            parsed = _parse_env_line(line)
            if not parsed:
                continue
            key, value = parsed
            if not os.environ.get(key):
                os.environ[key] = value


def safe_detail(value: str, limit: int = 400) -> str:
    return " ".join(str(value or "").split())[:limit]


def account_email(env_var: str, default_email: str) -> str:
    return os.environ.get(env_var, default_email).strip().lower() or default_email


def is_unresolved_env_placeholder(value: str) -> bool:
    return value.startswith("${") and value.endswith("}")


def profile_file(env_var: str, default_filename: str, default_profile_name: str = "staffanydatabot") -> Path:
    raw = os.environ.get(env_var, "").strip()
    if raw and not is_unresolved_env_placeholder(raw):
        return Path(raw).expanduser()
    profile_name = os.environ.get("HERMES_PROFILE", "").strip() or default_profile_name
    return Path.home() / ".hermes" / "profiles" / profile_name / default_filename


def load_json(path: Path, source_label: str, error_cls: Callable[..., Exception]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except FileNotFoundError as error:
        raise error_cls(f"Missing {source_label} OAuth file: {path}") from error
    except json.JSONDecodeError as error:
        raise error_cls(f"Invalid {source_label} OAuth JSON file: {path}") from error


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2))


def token_scopes(payload: dict[str, Any]) -> set[str]:
    raw = payload.get("scopes") or payload.get("scope") or []
    if isinstance(raw, str):
        return {item.strip() for item in raw.split() if item.strip()}
    if isinstance(raw, list):
        return {str(item).strip() for item in raw if str(item).strip()}
    return set()


def validate_scope(
    payload: dict[str, Any],
    required_scopes: set[str],
    source_label: str,
    error_cls: Callable[..., Exception],
) -> None:
    scopes = token_scopes(payload)
    if scopes and not required_scopes.issubset(scopes):
        missing = ", ".join(sorted(required_scopes.difference(scopes)))
        raise error_cls(f"{source_label} OAuth token is missing required scope(s): {missing}.")


def client_credentials(
    payload: dict[str, Any],
    client_secret_path: Path,
    source_label: str,
    error_cls: Callable[..., Exception],
) -> tuple[str, str]:
    client_id = str(payload.get("client_id") or "").strip()
    client_secret = str(payload.get("client_secret") or "").strip()
    if client_id and client_secret:
        return client_id, client_secret

    secret = load_json(client_secret_path, source_label, error_cls)
    installed = secret.get("installed") or secret.get("web") or {}
    client_id = str(installed.get("client_id") or "").strip()
    client_secret = str(installed.get("client_secret") or "").strip()
    if not client_id or not client_secret:
        raise error_cls(f"{source_label} OAuth client secret file is missing client_id/client_secret.")
    return client_id, client_secret


def refresh_access_token(
    payload: dict[str, Any],
    token_path: Path,
    client_secret_path: Path,
    user_agent: str,
    timeout_seconds: int,
    source_label: str,
    error_cls: Callable[..., Exception],
) -> str:
    refresh_token = str(payload.get("refresh_token") or "").strip()
    if not refresh_token:
        raise error_cls(f"{source_label} OAuth token has no refresh_token. Re-run OAuth setup.")

    client_id, client_secret = client_credentials(payload, client_secret_path, source_label, error_cls)
    data = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        str(payload.get("token_uri") or GOOGLE_OAUTH_TOKEN_URL),
        data=data,
        headers={"content-type": "application/x-www-form-urlencoded", "user-agent": user_agent},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            refreshed = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise error_cls(f"Google OAuth refresh failed: {error.code} {safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise error_cls(f"Google OAuth refresh timed out or failed: {reason}") from error

    access_token = str(refreshed.get("access_token") or "").strip()
    if not access_token:
        raise error_cls("Google OAuth refresh did not return an access token.")

    merged = dict(payload)
    merged.update(refreshed)
    merged["refresh_token"] = refresh_token
    if not merged.get("type"):
        merged["type"] = "authorized_user"
    write_json(token_path, merged)
    return access_token


def access_token(
    token_path: Path,
    client_secret_path: Path,
    required_scopes: set[str],
    user_agent: str,
    timeout_seconds: int,
    source_label: str,
    error_cls: Callable[..., Exception],
) -> str:
    payload = load_json(token_path, source_label, error_cls)
    validate_scope(payload, required_scopes, source_label, error_cls)
    token = str(payload.get("token") or payload.get("access_token") or "").strip()
    if token:
        return token
    return refresh_access_token(payload, token_path, client_secret_path, user_agent, timeout_seconds, source_label, error_cls)

