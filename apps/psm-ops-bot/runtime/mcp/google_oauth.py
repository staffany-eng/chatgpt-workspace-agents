"""Shared Google OAuth helpers for read-only PSM Ops adapters."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

GOOGLE_OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"
DEFAULT_PROFILE_NAME = "psmopsbot"
TOKEN_EXPIRY_BUFFER_SECONDS = 60


def safe_detail(value: str, limit: int = 400) -> str:
    text = " ".join(str(value or "").split())
    return text[:limit]


def account_email(env_var: str, default_email: str) -> str:
    import os

    return os.environ.get(env_var, default_email).strip().lower() or default_email


def is_unresolved_env_placeholder(value: str) -> bool:
    return value.startswith("${") and value.endswith("}")


def profile_file(env_var: str, default_filename: str, profile_name: str = DEFAULT_PROFILE_NAME) -> Path:
    import os

    raw = os.environ.get(env_var, "").strip()
    if raw and not is_unresolved_env_placeholder(raw):
        return Path(raw).expanduser()
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
    allowed_scopes: set[str],
    source_label: str,
    error_cls: Callable[..., Exception],
) -> None:
    scopes = token_scopes(payload)
    if scopes and not scopes.intersection(allowed_scopes):
        allowed = ", ".join(sorted(allowed_scopes))
        raise error_cls(f"{source_label} OAuth token is missing a permitted read scope: {allowed}.")


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
    expires_in = refreshed.get("expires_in")
    try:
        expires_in_int = int(expires_in) if expires_in is not None else 0
    except (TypeError, ValueError):
        expires_in_int = 0
    if expires_in_int > 0:
        new_expiry = datetime.now(timezone.utc) + timedelta(seconds=expires_in_int)
        merged["expiry"] = new_expiry.isoformat().replace("+00:00", "Z")
    else:
        # Refresh did not give us a fresh expiry — wipe the stale one so the
        # next call refreshes again instead of trusting the old value.
        merged.pop("expiry", None)
    write_json(token_path, merged)
    return access_token


def _token_expired(payload: dict[str, Any]) -> bool:
    raw = payload.get("expiry") or payload.get("expires_at")
    if not raw:
        # No expiry info recorded — treat as expired so the caller refreshes
        # rather than handing the API a possibly-stale token.
        return True
    text = str(raw).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        expires_at = datetime.fromisoformat(text)
    except ValueError:
        return True
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) >= expires_at - timedelta(seconds=TOKEN_EXPIRY_BUFFER_SECONDS)


def access_token(
    token_path: Path,
    client_secret_path: Path,
    allowed_scopes: set[str],
    user_agent: str,
    timeout_seconds: int,
    source_label: str,
    error_cls: Callable[..., Exception],
) -> str:
    payload = load_json(token_path, source_label, error_cls)
    validate_scope(payload, allowed_scopes, source_label, error_cls)
    token = str(payload.get("token") or payload.get("access_token") or "").strip()
    if token and not _token_expired(payload):
        return token
    return refresh_access_token(payload, token_path, client_secret_path, user_agent, timeout_seconds, source_label, error_cls)


def request_json(
    api_base_url: str,
    path: str,
    params: dict[str, Any],
    access_token: str,
    user_agent: str,
    timeout_seconds: int,
    source_label: str,
    error_cls: Callable[..., Exception],
) -> dict[str, Any]:
    query = urllib.parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
    url = f"{api_base_url}{path}"
    if query:
        url = f"{url}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "authorization": f"Bearer {access_token}",
            "accept": "application/json",
            "user-agent": user_agent,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise error_cls(f"{source_label} API failed: {error.code} {safe_detail(detail)}", error.code) from error
    except (urllib.error.URLError, socket.timeout, TimeoutError) as error:
        reason = getattr(error, "reason", error)
        raise error_cls(f"{source_label} API request timed out or failed: {reason}") from error
