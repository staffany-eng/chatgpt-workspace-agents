from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from profile_env import load_profile_env


SEARCH_SCRIPT_PATH = "f/rev_ops/search_billing_main_deals"
PREFLIGHT_SCRIPT_PATH = "f/rev_ops/preflight_create_sub_deal_request"
PREVIEW_SCRIPT_PATH = "f/rev_ops/create_sub_deal_and_service_agreement"
APPLY_PREFLIGHT_UPDATES_SCRIPT_PATH = "f/rev_ops/apply_preflight_updates"
SEND_SERVICE_AGREEMENT_SCRIPT_PATH = "f/rev_ops/send_service_agreement"
REQUEST_TIMEOUT_SECONDS = 30


@dataclass(frozen=True)
class WindmillConfig:
    base_url: str
    workspace_id: str
    token: str


def get_config() -> WindmillConfig:
    load_profile_env("revopsbot")
    base_url = os.environ.get("REVOPS_WINDMILL_BASE_URL", "").strip().rstrip("/")
    workspace_id = os.environ.get("REVOPS_WINDMILL_WORKSPACE_ID", "").strip()
    token = os.environ.get("REVOPS_WINDMILL_TOKEN", "").strip()
    missing = [
        name
        for name, value in {
            "REVOPS_WINDMILL_BASE_URL": base_url,
            "REVOPS_WINDMILL_WORKSPACE_ID": workspace_id,
            "REVOPS_WINDMILL_TOKEN": token,
        }.items()
        if not value
    ]
    if missing:
        raise ValueError(f"Missing RevOps Windmill env: {', '.join(missing)}")
    if not base_url.startswith(("http://", "https://")):
        raise ValueError("REVOPS_WINDMILL_BASE_URL must start with http:// or https://")
    return WindmillConfig(base_url=base_url, workspace_id=workspace_id, token=token)


def check_windmill_revops_config() -> dict[str, Any]:
    try:
        config = get_config()
    except Exception as exc:
        return {
            "ok": False,
            "status": "blocked",
            "reason": str(exc),
        }
    return {
        "ok": True,
        "status": "configured",
        "base_url": config.base_url,
        "workspace_id": config.workspace_id,
        "token_configured": True,
    }


def search_billing_main_deals(
    search: str = "",
    stage_ids: list[str] | None = None,
    deal_motions: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    payload = {
        "search": search,
        "stage_ids": stage_ids or [],
        "deal_motions": deal_motions or [],
        "limit": limit,
        "offset": offset,
    }
    return run_windmill_script(SEARCH_SCRIPT_PATH, payload)


def preflight_create_sub_deal_request(request_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    return run_windmill_script(PREFLIGHT_SCRIPT_PATH, {"request": request_payload})


def preflight_create_sub_deal_request_json(request_json: str) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return preflight_create_sub_deal_request(request_payload)


def preview_create_sub_deal_and_service_agreement(request_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    payload = {
        "request": request_payload,
        "dry_run": True,
    }
    return run_windmill_script(PREVIEW_SCRIPT_PATH, payload)


def preview_create_sub_deal_and_service_agreement_json(request_json: str) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return preview_create_sub_deal_and_service_agreement(request_payload)


def apply_preflight_updates(request_payload: dict[str, Any], dry_run: bool = True) -> dict[str, Any]:
    """Apply approved HubSpot readiness updates through Windmill.

    The Windmill script validates approval metadata, allowed properties, concrete
    proposal values, and current HubSpot values before applying any update.
    """

    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    payload = {
        "request": request_payload,
        "dry_run": bool(dry_run),
    }
    return run_windmill_script(APPLY_PREFLIGHT_UPDATES_SCRIPT_PATH, payload)


def apply_preflight_updates_json(request_json: str, dry_run: bool = True) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return apply_preflight_updates(request_payload, dry_run=dry_run)


def execute_create_sub_deal_and_service_agreement(request_payload: dict[str, Any]) -> dict[str, Any]:
    """Execute approved create-sub-deal/service-agreement request through Windmill.

    Live execution remains guarded by the Windmill script. It requires
    approval.status=approved, approval.approvedBy, and the exact
    approval.confirmationText returned by the preview step.
    """

    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    payload = {
        "request": request_payload,
        "dry_run": False,
    }
    return run_windmill_script(PREVIEW_SCRIPT_PATH, payload)


def execute_create_sub_deal_and_service_agreement_json(request_json: str) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return execute_create_sub_deal_and_service_agreement(request_payload)


def preview_send_service_agreement(request_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    payload = {
        "request": request_payload,
        "dry_run": True,
    }
    return run_windmill_script(SEND_SERVICE_AGREEMENT_SCRIPT_PATH, payload)


def preview_send_service_agreement_json(request_json: str) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return preview_send_service_agreement(request_payload)


def execute_send_service_agreement(request_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(request_payload, dict):
        raise ValueError("request_payload must be an object")
    payload = {
        "request": request_payload,
        "dry_run": False,
    }
    return run_windmill_script(SEND_SERVICE_AGREEMENT_SCRIPT_PATH, payload)


def execute_send_service_agreement_json(request_json: str) -> dict[str, Any]:
    try:
        request_payload = json.loads(request_json)
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "status": "invalid_json",
            "error": str(exc),
        }
    return execute_send_service_agreement(request_payload)


def run_windmill_script(script_path: str, payload: dict[str, Any]) -> dict[str, Any]:
    config = get_config()
    encoded_path = "/".join(parse.quote(part, safe="") for part in script_path.split("/"))
    workspace = parse.quote(config.workspace_id, safe="")
    url = f"{config.base_url}/api/w/{workspace}/jobs/run_wait_result/p/{encoded_path}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {config.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
    except error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Windmill script failed: HTTP {exc.code}: {response_body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Windmill request failed: {exc.reason}") from exc

    if not response_body:
        return {"ok": True, "result": None}
    try:
        parsed = json.loads(response_body)
    except json.JSONDecodeError:
        return {"ok": True, "result": response_body}
    if isinstance(parsed, dict):
        return parsed
    return {"ok": True, "result": parsed}
